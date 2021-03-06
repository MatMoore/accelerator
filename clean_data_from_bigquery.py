import pandas as pd
import nltk
from nltk.tokenize import wordpunct_tokenize
from nltk.stem.porter import PorterStemmer
import sys
import os

porter_stemmer = PorterStemmer()


def normalise_search_terms(terms):
    tokens = wordpunct_tokenize(terms)
    return ' '.join([porter_stemmer.stem(token) for token in tokens])


def filter_out_queries_with_not_enough_sessions(df):
    """
    The number of sessions retrieve will vary by search term.
    The volume of searches for a particular term may vary over time.

    I'm just going to ignore anything where I haven't pulled back enough sessions.
    """
    queries_before = df.searchTerm.nunique()

    term_summary = df.groupby('searchTerm').agg({'searchSessionId': lambda x: x.nunique()})
    enough_sessions = term_summary[term_summary.searchSessionId > 1000]
    queries_after = len(enough_sessions.index)

    if queries_after < queries_before:
        print(f'Filtered out {queries_before - queries_after} queries with less than 1000 sessions')
        print(f'There are now {queries_after} queries in the dataset')

    return df[df.searchTerm.isin(enough_sessions.index)]


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python clean_data_from_bigquery.py [input_filename] [output_filename]')
        sys.exit(1)

    # There are a handful of searches for literally "null"
    # Don't try and interpret that
    df = pd.read_csv(sys.argv[1], na_filter=False)

    print('Renaming columns')
    df = df.rename(
        {
            'ga:productSku': 'contentIdOrPath',
            'linkPosition': 'rank',
            'sessionId': 'searchSessionId',
            'searchTerm': 'originalSearchTerm'
        }, axis='columns'
    )

    df['searchTerm'] = df.originalSearchTerm.apply(normalise_search_terms)
    #df = filter_out_queries_with_not_enough_sessions(df)

    print(f'There are {df.searchSessionId.nunique()} unique sessions in the dataset')

    df.to_csv(sys.argv[2], index=False)