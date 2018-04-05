import pandas as pd
import sys
import os

def combine_pages(datadir):
    parts = os.listdir(datadir)

    df_from_each_file = (pd.read_csv(datadir + f) for f in parts)
    return pd.concat(df_from_each_file, ignore_index=True)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python clean_data_from_api.py [data dir] [output_filename]')
        sys.exit(1)

    datadir = sys.argv[1]
    output_filename = sys.argv[2]

    print(f'Combining CSVs in {datadir}')
    df = combine_pages(datadir)

    print(f'Combined {len(df)} rows (approx {len(df) // 20} sessions)')

    # Remove ID column I forgot to remove from the CSVs
    df.drop(df.columns[[0]], axis=1, inplace=True)

    # The hour/CTR columns aren't useful right now
    df.drop(['ga:hour', 'ga:productListCTR'], axis=1, inplace=True)

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

    # Assign a session ID to each unique combination of (userId, searchTerm)
    # This is not perfect, because the user could return to the same search multiple times,
    # and we just treat it as one session
    df['searchSessionId'] = df[['userId', 'searchTerm']].apply(lambda x: '_'.join(x.map(str)), axis=1)

    # We don't actually need this if we have a session ID
    df.drop(['userId'], axis=1, inplace=True)

    # --- Unadressed problems ---
    #
    # 1. Since we query by product, instead of by session, we may get incomplete sessions at the start
    #    and end of the time period.
    #
    # 2. Similar looking search terms are considered unique
    #
    # 3. I mangled the user ID since the ga.py script treats it as a float. This should be fine as long as it
    #    preserves uniqueness.

    df.to_csv(output_filename, index=False)