"""
Split the data into training and test datasets.

We do this on a per query level, because each query is independent, and should
not be over or underrepresented in the training set.

TODO: investigate variation in persistantness for each query,
      and consider preserving this in the training/test split
"""
import pandas as pd
from sklearn.model_selection import train_test_split

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