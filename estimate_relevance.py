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
from database import setup_database, get_searches, get_content_items, get_clicked_urls, get_skipped_urls
from split_data import training_and_test
from checks import SeriesProperties, DataFrameChecker
from uncertainty import product_relative_error, ratio_relative_error, sum_error
from clean_data_from_bigquery import normalise_search_terms

logging.basicConfig(filename='estimate_relevance.log',level=logging.INFO)


def calculate_examined(documents):
    documents['cov_clicked_skipped'] = documents.corr()['clicked']['skipped'] * documents['skipped_error'] * documents['clicked_error']
    documents['examined'] = documents.skipped + documents.clicked
    documents['examined_error'] = sum_error(
        documents.clicked_error,
        documents.skipped_error,
        covariance=documents.cov_clicked_skipped
    )

    checker = DataFrameChecker(documents)
    checker.column('examined').complete()
    checker.column('clicked').less_than_or_equal_to_column('examined')
    checker.column('skipped').less_than_or_equal_to_column('examined')
    checker.column('examined_error').greater_than_or_equal_to_column('clicked_error')
    checker.column('examined_error').greater_than_or_equal_to_column('skipped_error')


def calculate_attractiveness(documents):
    logging.info('Calculating attractiveness parameters')

    documents['cov_clicked_examined'] = documents.corr()['clicked']['examined'] * documents['clicked_error'] * documents['examined_error']

    documents['attractiveness'] = documents.clicked.divide(documents.examined)
    documents['attractiveness_error'] = documents.attractiveness * ratio_relative_error(
        documents.clicked, documents.examined,
        documents.clicked_error, documents.examined_error,
        covariance=documents.cov_clicked_examined
    )

    checker = DataFrameChecker(documents)
    checker.column('attractiveness').complete().within_range(0, 1)
    checker.column('attractiveness_error').less_than_or_equal_to_column('attractiveness')


def calculate_satisfyingness(documents):
    logging.info('Calculating satisfyingness parameters')

    documents['cov_chosen_clicked'] = documents.corr()['chosen']['clicked'] * documents['chosen_error'] * documents['clicked_error']

    # Some documents have never been clicked, so this can divide by zero. Just set these to 0. They have
    # zero relevance.
    documents['satisfyingness'] = documents.chosen.divide(documents.clicked).fillna(0)

    documents['satisfyingness_error'] = documents.satisfyingness * ratio_relative_error(
        documents.chosen, documents.clicked,
        documents.chosen_error, documents.clicked_error,
        covariance=documents.cov_chosen_clicked
    )

    checker = DataFrameChecker(documents)
    checker.column('satisfyingness').complete().within_range(0, 1)
    checker.column('satisfyingness_error').less_than_or_equal_to_column('satisfyingness')


def calculate_relevance(documents):
    logging.info('Calculating relevance')

    documents['cov_attractiveness_satisfyingness'] = documents.corr()['attractiveness']['satisfyingness'] * documents['attractiveness_error'] * documents['satisfyingness_error']

    documents['relevance'] = documents.attractiveness * documents.satisfyingness
    documents['relevance_error'] = documents.relevance * product_relative_error(
        a=documents.attractiveness,
        b=documents.satisfyingness,
        a_err=documents.attractiveness_error,
        b_err=documents.satisfyingness_error,
        covariance=documents.cov_attractiveness_satisfyingness
    )

    relative_error = (documents.relevance_error / documents.relevance).replace(np.inf, 0).fillna(0)
    relative_error_a = (documents.attractiveness_error / documents.attractiveness).replace(np.inf, 0).fillna(0)
    relative_error_s = (documents.satisfyingness_error / documents.satisfyingness).replace(np.inf, 0).fillna(0)

    checker = DataFrameChecker(documents)
    checker.column('relevance').complete().within_range(0, 1)

    # Relevance error should be greater than the component errors
    if sum((documents.relevance > 0) & (relative_error_a > relative_error)) > 0:
        import pdb; pdb.set_trace()
    if sum((documents.relevance > 0) & (relative_error_s > relative_error)) > 0:
        import pdb; pdb.set_trace()

    documents['relevance_low'] = (documents.relevance - documents.relevance_error).clip_lower(0)


class SimplifiedDBNModel:
    @staticmethod
    def from_csv(doc_params_csv_file):
        doc_params = pd.read_csv(doc_params_csv_file, index_col=['search_term_lowercase', 'result'])
        return SimplifiedDBNModel(doc_params)

    def to_csv(self, csv_file, **kwargs):
        self.document_params.to_csv(csv_file, **kwargs)

    def __init__(self, document_params=None):
        self.document_params = document_params

    def train(self, training_set):
        """
        Train the model. All input datasets should be indexed by the search ID from the DB.
        """
        # Augment the training set with clicked and skipped urls
        # this is really hacky but including these in the passed in dataset made things more complicated
        clicked_urls = get_clicked_urls(conn)
        skipped_urls = get_skipped_urls(conn)

        clicked_urls = clicked_urls[clicked_urls.index.isin(training_set.index)]
        skipped_urls = skipped_urls[skipped_urls.index.isin(training_set.index)]

        clicked_urls = clicked_urls.groupby(['search_term_lowercase', 'result']).size()
        skipped_urls = skipped_urls.groupby(['search_term_lowercase', 'result']).size()

        chosen_urls = training_set.groupby(['search_term_lowercase', 'final_click_url']).size()
        chosen_urls.index.names = ['search_term_lowercase', 'result']

        documents = pd.DataFrame({
            'clicked': clicked_urls,
            'skipped': skipped_urls,
            'chosen': chosen_urls
        })

        documents['clicked'] = documents.clicked.fillna(0)
        documents['clicked_error'] = documents.clicked.pow(1/2)

        documents['skipped'] = documents.skipped.fillna(0)
        documents['skipped_error'] = documents.skipped.pow(1/2)

        documents['chosen'] = documents.chosen.fillna(0)
        documents['chosen_error'] = documents.chosen.pow(1/2)

        checker = DataFrameChecker(documents)
        checker.column('clicked').complete()
        checker.column('skipped').complete()
        checker.column('chosen').complete()

        calculate_examined(documents)
        calculate_attractiveness(documents)
        calculate_satisfyingness(documents)
        calculate_relevance(documents)

        self.document_params = documents

    def relevance(self, query):
        """
        Calculate the relevance of all documents that have been returned by a query
        """
        if self.document_params is None:
            # This class is a mess, sorry
            raise Exception('Untrained model')

        try:
            return self.document_params.loc[query].relevance_low.sort_values(ascending=False)
        except AttributeError:
            # HACK: older CSV files I created didn't precompute the relevance
            return self.document_params.loc[query].attractiveness.multiply(self.document_params.loc[query].satisfyingness).sort_values(ascending=False)


if __name__ == '__main__':
    # This is a mess of circular dependencies
    from evaluate_model import QueryDocumentRanker, ModelTester

    print('Setting up database...')
    conn = setup_database()

    df = get_searches(conn)

    print('Queries')
    queries = df.search_term_lowercase.unique()

    print('Splitting')
    training_set, test_set = training_and_test(df)

    debug = os.environ.get('DEBUG')

    del df

    if debug:
        print('DEBUG MODE: training one query only')
        training_set = training_set[training_set.search_term_lowercase == 'self assessment']
        test_set = test_set[test_set.search_term_lowercase == 'self assessment']

    content_items = get_content_items(conn)

    print('Training')
    model = SimplifiedDBNModel()
    model.train(training_set)

    model.to_csv('data/june10/my-sdbn_model.csv')
