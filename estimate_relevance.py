"""
Extract sessions, split into training and test sets, then train
a dynamic bayesian network to predict what users click on last.
We assume that the user continued clicking on things until they
found what they were looking for.
"""
import pandas as pd
import numpy as np
import sys
import os
import logging
from database import setup_database, get_searches, get_clicked_urls, get_passed_over_urls, get_content_items
from sklearn.model_selection import train_test_split
from checks import SeriesProperties

logging.basicConfig(filename='estimate_relevance.log',level=logging.INFO)


def training_and_test(df):
    """
    Split training and test data for each query
    """
    train = []
    test = []
    for query in queries:
        query_data = df[df.search_term_lowercase == query]
        query_train, query_test = train_test_split(query_data, test_size=0.25)
        train.append(query_train)
        test.append(query_test)

    training_set = pd.concat(train)
    test_set = pd.concat(test)

    return training_set, test_set


class SimplifiedDBNModel:
    def train(self, training_set, clicked_urls, passed_over_urls):
        """
        Train the model. All input datasets should be indexed by the search ID from the DB.
        """
        clicked_urls = clicked_urls[clicked_urls.index.isin(training_set.index)]
        clicked_urls = clicked_urls.groupby(['search_term_lowercase', 'result']).size()

        passed_over_urls = passed_over_urls[passed_over_urls.index.isin(training_set.index)]
        passed_over_urls = passed_over_urls.groupby(['search_term_lowercase', 'result']).size()

        chosen_urls = training_set.groupby(['search_term_lowercase', 'final_click_url']).size()
        chosen_urls.index.names = ['search_term_lowercase', 'result']

        documents = pd.DataFrame({
            'clicked': clicked_urls,
            'passed_over': passed_over_urls,
            'chosen': chosen_urls
        })

        documents['clicked'] = documents.clicked.fillna(0)
        documents['clicked_error'] = documents.clicked.pow(1/2)

        documents['passed_over'] = documents.passed_over.fillna(0)
        documents['passed_over_error'] = documents.passed_over.pow(1/2)

        documents['chosen'] = documents.chosen.fillna(0)
        documents['chosen_error'] = documents.chosen.pow(1/2)

        documents['examined'] = documents.passed_over + documents.clicked

        print(f'Ignoring {sum(documents.examined < 50)} query/document pairs out of {len(documents)}')
        documents = documents[documents.examined > 50] # arbitrary number

        documents['attractiveness'] = documents.clicked.divide(documents.examined)

        # Some documents have never been clicked, so this can divide by zero. Just set these to 0. They have
        # zero relevance.
        documents['satisfyingness'] = documents.chosen.divide(documents.clicked).fillna(0)

        SeriesProperties(documents, 'clicked') \
            .complete() \
            .less_than_or_equal_to_column('examined')

        SeriesProperties(documents, 'clicked_error') \
            .complete() \
            .less_than_or_equal_to_column('clicked')

        SeriesProperties(documents, 'chosen') \
            .complete() \
            .less_than_or_equal_to_column('clicked')

        SeriesProperties(documents, 'chosen_error') \
            .complete() \
            .less_than_or_equal_to_column('chosen')

        SeriesProperties(documents, 'passed_over') \
            .complete() \
            .less_than_or_equal_to_column('examined')

        SeriesProperties(documents, 'passed_over_error') \
            .complete() \
            .less_than_or_equal_to_column('passed_over')

        SeriesProperties(documents, 'attractiveness') \
            .complete() \
            .within_range(0, 1)


        SeriesProperties(documents, 'satisfyingness') \
            .complete() \
            .within_range(0, 1)

        self.document_params = documents

    def relevance(self, query):
        """
        Calculate the relevance of all documents that have been returned by a query
        """
        query_attractiveness = self.document_params.attractiveness[query]
        query_satisfyingness = self.document_params.satisfyingness[query]

        relevance = query_attractiveness.multiply(query_satisfyingness)

        return relevance.sort_values(ascending=False)


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
        return self._evaluate(test_set)

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
            #print(f"User clicked on something that wasn't in the training set (query={query}, doc={test_row.final_click_url})")
            return 0

        rubbish_urls = [url for url in test_row.clicked_urls if url != final_click_url]

        saved_clicks_count = 0
        for url in rubbish_urls:
            try:
                rank = new_ranking[url]
            except KeyError:
                #print(f"User clicked on something that wasn't in the training set (query={query}, doc={url})")
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
            #print(f"User clicked on something that wasn't in the training set (query={query}, doc={test_row.final_click_url})")

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

    queries = df.search_term_lowercase.unique()

    training_set, test_set = training_and_test(df)

    del df

    content_items = get_content_items(conn)

    model = SimplifiedDBNModel()
    model.train(
        training_set,
        get_clicked_urls(conn, input_filename),
        get_passed_over_urls(conn, input_filename),
    )

    tester = ModelTester(model)
    evaluation = tester.evaluate(test_set)

    print(f'Median change in rank: {evaluation.change_in_rank.median()} (positive number => majority of users save time)')
    print(f'Median saved clicks: {evaluation.saved_clicks.median()}')

    ranker = QueryDocumentRanker(model)
    example = model.relevance('self assessment')
    example_df = example.to_frame('relevance').join(content_items, how='left').loc[:, ['title', 'relevance']].sort_values('relevance', ascending=False)

    evaluation.to_csv('data/week6/2018-04-26-test_set.csv')
    model.document_params.to_csv('data/week6/2018-04-26-model.csv')

    import pdb; pdb.set_trace()