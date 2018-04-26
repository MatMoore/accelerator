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

def ratio_error(num, den, num_err, den_err, covariance=0):
    """
    Relative error of a ratio

    If either num or den are zero, their contributions to the error will be zero
    """
    num_term = num_err.divide(num).replace(np.inf, 0).fillna(0).pow(2)
    den_term = den_err.divide(den).replace(np.inf, 0).fillna(0).pow(2)
    covariance_term = 2 * np.divide(covariance, (num * den)).replace(np.inf, 0).fillna(0)
    import pdb; pdb.set_trace()
    variance = num_term + den_term - covariance_term
    return variance.pow(1/2)

def product_error(a, b, a_err, b_err, covariance=0):
    """
    Relative error of a product of two values

    If either a or b are zero, their contributions to the error will be zero
    """
    a_term = a_err.divide(a).replace(np.inf, 0).fillna(0).pow(2)
    b_term = b_err.divide(b).replace(np.inf, 0).fillna(0).pow(2)
    covariance_term = 2 * np.divide(covariance, (a * b)).replace(np.inf, 0).fillna(0)

    variance = a_term + b_term + covariance_term
    return variance.pow(1/2)

def sum_error(a_err, b_err, covariance=0):
    """
    Absolute error of a sum of two values
    """
    variance = a_err.pow(2) + b_err.pow(2) + 2 * covariance
    return variance.pow(1/2)


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

        passed_over_clicked_cov = documents.passed_over.cov(documents.clicked)
        documents['examined'] = documents.passed_over + documents.clicked
        documents['examined_error'] = sum_error(documents.passed_over_error, documents.clicked_error, passed_over_clicked_cov)

        clicked_examined_cov = documents.clicked.cov(documents.examined)
        documents['attractiveness'] = documents.clicked.divide(documents.examined)
        documents['attractiveness_error'] = ratio_error(documents.clicked, documents.examined, documents.clicked_error, documents.examined_error, clicked_examined_cov)

        # Some documents have never been clicked, so this can divide by zero. Just set these to 0. They have
        # zero relevance.
        chosen_clicked_cov = documents.chosen.cov(documents.clicked)
        documents['satisfyingness'] = documents.chosen.divide(documents.clicked).fillna(0)
        documents['satisfyingness_error'] = documents.satisfyingness * ratio_error(documents.chosen, documents.clicked, documents.chosen_error, documents.clicked_error, chosen_clicked_cov)

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

        SeriesProperties(documents, 'attractiveness_error') \
            .complete()

        SeriesProperties(documents, 'satisfyingness') \
            .complete() \
            .within_range(0, 1)

        SeriesProperties(documents, 'satisfyingness_error') \
            .complete()

        self.document_params = documents

    def relevance(self, query):
        """
        Calculate the relevance of all documents that have been returned by a query
        """
        query_attractiveness = self.document_params.attractiveness[query]
        query_satisfyingness = self.document_params.satisfyingness[query]
        query_attractiveness_error = self.document_params.attractiveness_error[query]
        query_satisfyingness_error = self.document_params.satisfyingness_error[query]

        attractiveness_satisfyingness_cov = query_attractiveness.cov(query_satisfyingness)

        relevance = query_attractiveness.multiply(query_satisfyingness)
        relevance_error = relevance * product_error(query_attractiveness, query_satisfyingness, query_attractiveness_error, query_satisfyingness_error, attractiveness_satisfyingness_cov)

        lower_bound = relevance.subtract(relevance_error).clip_lower(0)

        return pd.DataFrame(
            {'value': relevance, 'error': relevance_error, 'lower': lower_bound},
            index=relevance.index
        ).sort_values('lower', ascending=False)


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
            ranking = self.model.relevance(query).lower.rank(method= 'min', ascending=False)
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
        return self._evaluate(test_set).loc[:, ['saved_clicks', 'change_in_rank']]

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
    evaluation = tester.evaluate(test_set)

    print(f'Median change in rank: {evaluation.change_in_rank.median()} (positive number => majority of users save time)')
    print(f'Median saved clicks: {evaluation.change_in_rank.median()}')

    ranker = QueryDocumentRanker(model)
    example = model.relevance('self assessment')
    example_df = example.join(content_items, how='left').loc[:, ['title', 'value', 'error', 'lower']].sort_values('lower', ascending=False)

    import pdb; pdb.set_trace()