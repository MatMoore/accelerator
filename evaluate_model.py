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
from sklearn.model_selection import train_test_split
from checks import SeriesProperties, DataFrameChecker
from uncertainty import product_relative_error, ratio_relative_error, sum_error
from clean_data_from_bigquery import normalise_search_terms
from estimate_relevance import SimplifiedDBNModel
from pyclick.click_models import SDBN

logging.basicConfig(filename='estimate_relevance.log',level=logging.INFO)


class PyClickModelAdapter:
    """
    Takes a pyclick model and wraps it in a class that can calculate
    relevance estimates from the model's params.
    """
    @staticmethod
    def from_json(json_file):
        model = SDBN()
        with open(json_file) as f:
            json_str = f.read()
        model.from_json(json_str)
        return PyClickModelAdapter(model)

    def __init__(self, model):
        self.model = model

    def relevance(self, query):
        attr_param = self.model.param_names.attr
        documents = self.model.params[attr_param]._container[query].keys()
        return self.predict_relevance(query, documents)

    def predict_relevance(self, query, documents):
        return pd.Series(
            (self.model.predict_relevance(query, document) for document in documents),
            index=documents
        ).sort_values(ascending=False)


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

        But:
        - More of the tests set have seen the results closer to the top
        - Less of the test set have seen the results closer to the bottom
        - The distribution of final clicks is biased by this

        To counteract this, weight improvements higher if the original
        rank was higher.

        TODO: does this make any sense?
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

        return (old_rank - new_rank)


if __name__ == '__main__':
    conn = setup_database()
    content_items = get_content_items(conn)

    pyclick_model = PyClickModelAdapter.from_json('data/june10/sdbn_model.json')

    # NOTE: this comes from an earlier dataset - some queries are different. Should rerun this
    my_model = SimplifiedDBNModel.from_csv('data/week7/pyclick-comparison/2018-04-26-model-no-uncertainty.csv')

    pyclick_ranker = QueryDocumentRanker(pyclick_model)
    my_model_ranker = QueryDocumentRanker(my_model)

    queries = my_model.document_params.index.get_level_values(0).unique()
    print(f'loaded {len(queries)} queries')

    for query in queries:
        pyclick_rank = pyclick_ranker.rank(query)
        my_rank = my_model_ranker.rank(query)

        df1 = my_rank.to_frame()
        df2 = pyclick_rank.to_frame()
        results = df1.join(df2, lsuffix='mine', rsuffix='pyclick').join(content_items)



    # # How does the new ranker do against the saved-effort metrics?
    # tester = ModelTester(ranker)
    # evaluation = tester.evaluate(test)

    # print(f'Median change in rank: {evaluation.change_in_rank.mean()}')
    # print(f'Median saved clicks: {evaluation.saved_clicks.median()}')