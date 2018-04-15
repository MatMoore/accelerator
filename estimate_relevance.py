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
from database import setup_database, get_searches, get_clicked_urls, get_passed_over_urls
from sklearn.model_selection import train_test_split

logging.basicConfig(filename='estimate_relevance.log',level=logging.INFO)


class SimplifiedDBNModel:
    def train(self, training_set, clicked_urls, passed_over_urls):
        """
        Train the model. All input datasets should be indexed by the search ID from the DB.
        """
        clicked_urls = clicked_urls[clicked_urls.index.isin(training_set.index)]
        clicked_urls = clicked_urls.groupby(['search_term_lowercase', 'result']).size()

        passed_over_urls = passed_over_urls[passed_over_urls.index.isin(training_set.index)]
        passed_over_urls = passed_over_urls.groupby(['search_term_lowercase', 'result']).size()

        final_clicked_urls = training_set.groupby(['search_term_lowercase', 'final_click_url']).size()
        final_clicked_urls.index.names = ['search_term_lowercase', 'result']

        examined_urls = (passed_over_urls + clicked_urls).fillna(passed_over_urls).fillna(clicked_urls)

        self.attractiveness = clicked_urls.divide(examined_urls, fill_value=0)
        self.satisfyingness = final_clicked_urls.divide(clicked_urls, fill_value=0)

    def new_ranking(self, query):
        """
        Rank all results for a query by relevance
        """
        return self.attractiveness[query].multiply(self.satisfyingness[query], fill_value=0).sort_values(ascending=False)

    def predict_last_click(self, test_set):
        """
        predict the final clicked result for each query?
        """
        # TODO: make sure training set contains the same queries as the test set
        test_set = test_set.reindex(['final_click_url', 'search_term_lowercase'])

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

    model = SimplifiedDBNModel()
    model.train(
        training_set,
        get_clicked_urls(conn, input_filename),
        get_passed_over_urls(conn, input_filename),
    )

    model.new_ranking('self assessment')

    import pdb; pdb.set_trace()

    prediction = model.predict_last_click(
        test_set
    )