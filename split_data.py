"""
Split the data into training and test datasets.

We do this on a per query level, because each query is independent, and should
not be over or underrepresented in the training set.

TODO: investigate variation in persistentness for each query,
      and consider preserving this in the training/test split
"""
import pandas as pd
from sklearn.model_selection import train_test_split
from database import get_searches, setup_database
from ast import literal_eval
from pandas.util.testing import assert_frame_equal


def training_and_test(df):
    """
    Split training and test data for each query
    """
    queries = df.search_term_lowercase.unique()
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


def load_from_csv(training_file='data/training_set.csv', test_file='data/test_set.csv'):
    training = pd.read_csv(training_file, converters={'all_urls': literal_eval, 'clicked_urls': literal_eval})
    test = pd.read_csv(test_file, converters={'all_urls': literal_eval, 'clicked_urls': literal_eval})
    return training, test


def save_to_csv(training, test, training_file='data/training_set.csv', test_file='data/test_set.csv'):
    training.to_csv(training_file, index=False)
    test.to_csv(test_file, index=False)


if __name__ == '__main__':
    """
    Load sessions from the DB, split into training/test set,
    and save to CSVs so they can be read in by other scripts.
    """
    conn = setup_database()
    searches = get_searches(conn)

    training, test = train_test_split(searches)

    print(f'split into {len(training)} training rows and {len(test)} test rows')
    save_to_csv(training, test)
    training2, test2 = load_from_csv()

    print('testing output')
    assert_frame_equal(training.reset_index(drop=True), training2.reset_index(drop=True))
    assert_frame_equal(test.reset_index(drop=True), test2.reset_index(drop=True))
    print('ok')