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
from database import setup_database, get_searches, get_content_items
from sklearn.model_selection import train_test_split
from checks import SeriesProperties, DataFrameChecker
from uncertainty import product_relative_error, ratio_relative_error, sum_error

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
    checker.column('examined_error').less_than_or_equal_to_column('examined')


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
    checker.column('attractiveness').complete().within_range(0, 1)
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

    if sum(relative_error_a > relative_error ** 2) > 0:
        import pdb; pdb.set_trace()
    if sum(relative_error_s > relative_error ** 2) > 0:
        import pdb; pdb.set_trace()

    checker = DataFrameChecker(documents)
    checker.column('relevance').complete().within_range(0, 1)

class SimplifiedDBNModel:
    def train(self, training_set, min_examined=None):
        """
        Train the model. All input datasets should be indexed by the search ID from the DB.
        """

        # This creates a new row for each element in each clicked_urls list
        # It is ridiculously slow. Fix this!!!
        print('Begin magic')
        clicked_urls = training_set.loc[:, ['clicked_urls', 'search_term_lowercase']]
        clicked_urls = clicked_urls.set_index('search_term_lowercase').apply(lambda x: x.apply(pd.Series).stack()).reset_index()
        clicked_urls.drop('level_1', 1)
        clicked_urls = clicked_urls.rename({'clicked_urls': 'result'}, axis=1)
        clicked_urls = clicked_urls.groupby(['search_term_lowercase', 'result']).size()
        print('More magic')

        # Skipped means they didn't choose it but they examined it
        skipped_urls = training_set.loc[:, ['skipped_urls', 'search_term_lowercase']]
        skipped_urls = skipped_urls.set_index('search_term_lowercase').apply(lambda x: x.apply(pd.Series).stack()).reset_index()
        skipped_urls.drop('level_1', 1)
        skipped_urls = skipped_urls.rename({'skipped_urls': 'result'}, axis=1)
        skipped_urls = skipped_urls.groupby(['search_term_lowercase', 'result']).size()
        print('end magic')

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
        return self.document_params.loc[query].relevance.sort_values(ascending=False)


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
    def __init__(self, ranker):
        self.ranker = ranker

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
        test_set['saved_clicks'] = test_set.apply(self.count_saved_clicks, axis=1)
        test_set['change_in_rank'] = test_set.apply(self.change_in_rank_of_preferred_document, axis=1)

        return test_set

    def count_saved_clicks(self, test_row):
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

    def change_in_rank_of_preferred_document(self, test_row):
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
        training_set
    )

    tester = ModelTester(QueryDocumentRanker(model))
    evaluation = tester.evaluate(test_set)

    print(f'Median change in rank: {evaluation.change_in_rank.median()} (positive number => majority of users save time)')
    print(f'Median saved clicks: {evaluation.saved_clicks.median()}')

    ranker = QueryDocumentRanker(model)
    example = model.relevance('self assessment')
    example_df = example.to_frame('relevance').join(content_items, how='left').loc[:, ['title', 'relevance']].sort_values('relevance', ascending=False)

    evaluation.to_csv('data/week7/pyclick-comparison/2018-04-26-test_set-uncertainty.csv')
    model.document_params.to_csv('data/week7/pyclick-comparison/2018-04-26-model-uncertainty.csv')

    import pdb; pdb.set_trace()