"""
Extract sessions, split into training and test sets, then train
a dynamic bayesian network to predict what users click on last.
We assume that the user continued clicking on things until they
found what they were looking for.
"""
from collections import Counter
import pandas as pd
import sys
import os
import logging
from database import setup_database, get_searches, get_clicked_urls, get_passed_over_urls, get_content_items
from sklearn.model_selection import train_test_split

logging.basicConfig(filename='estimate_relevance.log',level=logging.INFO)


class SimplifiedDBNModel:
    def train(self, training_set, clicked_urls, passed_over_urls):
        """
        Train the model. All input datasets should be indexed by the search ID from the DB.
        """
        clicked_urls = clicked_urls[clicked_urls.index.isin(training_set.index)]
        clicked_urls = clicked_urls.groupby(['search_term_lowercase', 'result']).size()

        clicked_urls_error = clicked_urls.pow(1/2)

        passed_over_urls = passed_over_urls[passed_over_urls.index.isin(training_set.index)]
        passed_over_urls = passed_over_urls.groupby(['search_term_lowercase', 'result']).size()

        passed_over_urls_error = passed_over_urls.pow(1/2)

        final_clicked_urls = training_set.groupby(['search_term_lowercase', 'final_click_url']).size()
        final_clicked_urls.index.names = ['search_term_lowercase', 'result']

        final_clicked_urls_error = final_clicked_urls.pow(1/2)

        examined_urls = (passed_over_urls + clicked_urls).fillna(passed_over_urls).fillna(clicked_urls)
        examined_urls_error = (passed_over_urls_error ** 2 + clicked_urls_error ** 2).pow(1/2)

        attractiveness = clicked_urls.divide(examined_urls).fillna(0)
        satisfyingness = final_clicked_urls.divide(clicked_urls).fillna(0)

        attractiveness_error = attractiveness * (
            clicked_urls_error.divide(clicked_urls).fillna(0).pow(2).add(
                examined_urls_error.divide(examined_urls).fillna(0).pow(2),
                fill_value=0
            )
        ).pow(1/2)

        satisfyingness_error = satisfyingness * (
            final_clicked_urls_error.divide(final_clicked_urls).fillna(0).pow(2).add(
                clicked_urls_error.divide(clicked_urls).fillna(0).pow(2),
                fill_value=0
            )
        ).pow(1/2)

        self.attractiveness = attractiveness
        self.attractiveness_error = attractiveness_error
        self.satisfyingness = satisfyingness
        self.satisfyingness_error = satisfyingness_error

    def relevance(self, query):
        """
        Calculate the relevance of all documents that have been returned by a query

        TODO: this needs to take into account error: some documents have very low counts,
              so would have a large error. We should use the lower side of the error bar
              for relevance.
        """
        attractiveness = self.attractiveness[query]
        satisfyingness = self.satisfyingness[query]
        attractiveness_error = self.attractiveness_error[query]
        satisfyingness_error = self.satisfyingness_error[query]

        relevance = attractiveness.multiply(satisfyingness, fill_value=0).sort_values(ascending=False)

        relevance_error = relevance.multiply(
            attractiveness_error.divide(attractiveness).fillna(0).pow(2).add(
                satisfyingness_error.divide(satisfyingness).fillna(0).pow(2),
                fill_value=0
            ),
            fill_value=0
        ).pow(1/2)

        relevance = (relevance - relevance_error).clip(lower=0)
        return relevance


class QueryDocumentRanker:
    """
    Generates new rankings for queries based on a model that estimates relevance
    of each document. All rankings are cached in memory.
    """
    def __init__(self, trained_model):
        self.model = trained_model
        self.query_rankings = {}

    def rank(self, query):
        """
        Rank all results for a query by relevance
        """
        try:
            return self.query_rankings[query]
        except KeyError:
            ranking = self.model.relevance(query).rank(method= 'min', ascending=False)
            self.query_rankings[query] = ranking
            return ranking


class ModelTester:
    def __init__(self, trained_model):
        self.ranker = QueryDocumentRanker(trained_model)

    def evaluate(self, test_set):
        """
        Evaluate how well our model describes the test data.

        This calculates two metrics:
        - The number of saved clicks (known bad results that are avoided in the new ranking)
        - Change in rank of the user's preferred document (showing it higher reduces the
          number of URLs the user has to examine to find it)
        """
        return self._evaluate(test_set).loc[:, ['saved_clicks', 'change_in_rank']].describe()

    def _evaluate(self, test_set):
        # TODO: make sure training set contains the same queries as the test set(!)
        test_set['saved_clicks'] = test_set.apply(self._count_saved_clicks, axis=1)
        test_set['change_in_rank'] = test_set.apply(self._change_in_rank_of_preferred_document, axis=1)

        return test_set

    def _count_saved_clicks(self, test_row):
        """
        Evaluate the number of known-bad results that would be avoided if the model's
        preferred ranking was used (because those documents are now ranked below the final clicked one)

        In this model, every click except the last one is assumed to be bad.

        If a user clicked 1, 3, and 4, and the model's rank is 1, 4, 3, then the saved clicks is 1,
        because the user would not have needed to click document 3.

        This doesn't go negative even if the model ranks the preferred document at the bottom,
        because we assume the user keeps scanning through the results until they find a document
        they are satisfied with.
        """
        query = test_row.search_term_lowercase
        new_ranking = self.ranker.rank(query)

        final_click_url = test_row.final_click_url

        try:
            final_click_new_ranking = new_ranking[final_click_url]
        except KeyError:
            print(f"User clicked on something that wasn't in the training set (query={query}, doc={test_row.final_click_url})")
            return 0

        rubbish_urls = [url for url in test_row.clicked_urls if url != final_click_url]

        saved_clicks_count = 0
        for url in rubbish_urls:
            try:
                rank = new_ranking[url]
            except KeyError:
                print(f"User clicked on something that wasn't in the training set (query={query}, doc={url})")
                continue

            if rank > final_click_new_ranking:
                saved_clicks_count += 1

        return saved_clicks_count

    def _change_in_rank_of_preferred_document(self, test_row):
        """
        Work out how much the preferred document has gone up or down.
        A positive value indicates that the doc is closer to the top
        (so the user is assumed to examine less before finding it).
        A negative value indicates that the doc is further down the page.
        """
        query = test_row.search_term_lowercase
        new_ranking = self.ranker.rank(query)

        old_rank = test_row.final_click_rank

        try:
            new_rank = new_ranking[test_row.final_click_url]
        except KeyError:
            print(f"User clicked on something that wasn't in the training set (query={query}, doc={test_row.final_click_url})")

            # Since the doc didn't appear in the training set, we are not
            # really saying anything about its new rank. So just ignore it.
            return 0

        return old_rank - new_rank

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python estimate_relevance.py [original input csv]')
        sys.exit(1)

    print('Setting up database...')
    conn = setup_database()

    input_filename = sys.argv[1]

    df = get_searches(conn, input_filename)
    training_set, test_set = train_test_split(df, test_size=0.25)
    del df

    content_items = get_content_items(conn)

    model = SimplifiedDBNModel()
    model.train(
        training_set,
        get_clicked_urls(conn, input_filename),
        get_passed_over_urls(conn, input_filename),
    )

    tester = ModelTester(model)
    summary = tester.evaluate(test_set)

    import pdb; pdb.set_trace()