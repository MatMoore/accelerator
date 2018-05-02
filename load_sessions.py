"""
This takes a dataset of clicks and impressions, splits it by session, and loads
each session into a database.

For each session we should have a list of links that were clicked, and a complete
list of URLs that displayed above the final clicked link. If there are any gaps,
discard the session.
"""
from collections import Counter
import pandas as pd
import sys
import os
from collections import defaultdict
import logging
from database import insert_session_into_database, setup_database, record_dataset

logging.basicConfig(filename='load_sessions.log',level=logging.INFO)


def sessions_to_observations(df):
    """
    Map from (sessionId, searchTerm) to a list of all indexes relating to that session

    searchTerm is included because a user run multiple searches per session, and we
    want to consider them separately.
    """
    sessions = defaultdict(list)
    for index, row in df.iterrows():
        session = row['searchSessionId']
        search_term = row['searchTerm']
        sessions[(session, search_term)].append(index)

    return sessions


def session_data(input_data, session_map, session_id):
    """
    Return the clicks and impressions for a single session, highest rank first
    """
    indexes = session_map[session_id]
    rank_order = input_data.loc[indexes].sort_values(by=['rank'], ascending=False)
    return rank_order


def process_session(rank_order, invalid_counter):
    """
    Look at all clicks and impressions belonging to a session and
    transform it into a summary of the session.
    This is really slow.

    This discards any sessions where we don't have any clicks, or we don't
    have impressions for the stuff above the final click.
    """
    clicks = rank_order[rank_order.observationType == 'click']

    if not len(clicks):
        # Discard session if no clicks on first page
        logging.info('No clicks')
        invalid_counter['no_clicks'] += 1
        return None

    final_click_row = clicks.iloc[0]

    search_term = final_click_row['searchTerm']
    final_url_clicked = final_click_row['contentIdOrPath']
    final_rank = final_click_row['rank']

    passed_over = rank_order[(rank_order.observationType == 'impression') & (rank_order.loc[:, 'rank'] < final_rank)]

    passed_over_ranks = set(passed_over['rank'].tolist())
    if passed_over_ranks != set(range(1, final_rank)):
        # Discard session if missing impressions
        logging.info(f'Impression data incomplete for final rank {final_rank}:')
        logging.info(passed_over_ranks)
        invalid_counter['missing_impressions'] += 1
        return None

    passed_over_results = passed_over.contentIdOrPath.tolist()
    clicked_results = clicks.contentIdOrPath.tolist()

    session = {
        'searchSessionId': session_id,
        'searchTerm': search_term,
        'finalRank': final_rank.item(),
        'passedOverResults': passed_over_results,
        'clickedResults': clicked_results,
        'finalItemClicked': final_url_clicked,
    }

    logging.info(session)
    return session


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python load_sessions.py [input csv]')
        sys.exit(1)

    input_filename = sys.argv[1]

    print('Setting up database...')
    conn = setup_database()

    print('Loading input...')
    df = pd.read_csv(input_filename)

    print('Creating session map...')
    session_map = sessions_to_observations(df)

    print('Processing sessions...')
    dataset_id = record_dataset(conn, input_filename)

    invalid_counter = Counter()
    for session_id in session_map:
        logging.info(session_id)
        session_df = session_data(df, session_map, session_id)
        session_summary = process_session(session_df, invalid_counter=invalid_counter)

        if session_summary is None:
            continue

        try:
            insert_session_into_database(session_summary, conn, dataset_id=dataset_id)
        except Exception:
            logging.exception('Unable to insert into database: {session_summary}')
            invalid_counter['database_errors'] += 1

    print(f'Invalid sessions: {invalid_counter}')