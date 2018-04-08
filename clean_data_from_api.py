import pandas as pd
import sys
import os


def combine_pages(datadir):
    """
    The API only returns 1000 rows at a time, and I save each to a separate CSV file.
    """
    parts = os.listdir(datadir)

    def generate_files():
        for f in parts:
            print(f)
            yield pd.read_csv(datadir + f)

    return pd.concat(generate_files(), ignore_index=True)


def filter_out_queries_with_not_enough_sessions(df):
    """
    Because ga.py has a fixed date range, the number of sessions retrieved
    will vary by search term. The volume of searches for a particular term may
    vary over time.

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
        print('Usage: python clean_data_from_api.py [data dir] [output_filename]')
        sys.exit(1)

    datadir = sys.argv[1]
    output_filename = sys.argv[2]

    print(f'Combining CSVs in {datadir}')
    df = combine_pages(datadir)

    print(f'Combined {len(df)} rows')

    # Remove ID column I forgot to remove from the CSVs
    df.drop(df.columns[[0]], axis=1, inplace=True)

    # The hour/CTR columns aren't useful right now
    #df.drop(['ga:hour', 'ga:productListCTR'], axis=1, inplace=True)

    df = df.rename(
        {
            'ga:dimension95': 'userId',
            'ga:productSku': 'contentIdOrPath',
            'ga:productListPosition': 'rank',
            'ga:dimension71': 'searchTerm',
            'ga:productListViews': 'impressions',
            'ga:productListClicks': 'clicks'
        }, axis='columns'
    )

    # In Februrary 2018, there was a bug that caused the CLIENT_ID to be reported as [object object].
    # this causes a bunch of sessions to be smooshed together.
    # This was fixed a couple of weeks later, but there are still some sessions that reported this value
    # later than this.
    # We should just drop this data as it's unusable.
    df = df[df.userId != '[object Object]']

    # Assign a session ID to each unique combination of (userId, searchTerm)
    # This is not perfect, because the user could return to the same search multiple times,
    # and we just treat it as one session
    df['searchSessionId'] = df[['userId', 'searchTerm']].apply(lambda x: '_'.join(x.map(str)), axis=1)

    # We don't actually need this column anymore as it's included in the session ID
    df.drop(['userId'], axis=1, inplace=True)

    df = filter_out_queries_with_not_enough_sessions(df)

    print(f'There are {df.searchSessionId.nunique()} unique sessions in the dataset')

    # --- Unadressed problems ---
    #
    # 1. Since we query by product, instead of by session, we may get incomplete sessions at the start
    #    and end of the time period.
    #
    # 2. Similar looking search terms are considered unique (including pluralisations of the same term)
    #
    # 3. I mangled the user ID since the ga.py script treats it as a float. This should be fine as long as it
    #    preserves uniqueness.

    df.to_csv(output_filename, index=False)