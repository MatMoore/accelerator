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
import sqlalchemy
from sqlalchemy import Table, Column, BigInteger, Integer, Boolean, String, Date, MetaData, ForeignKey, ARRAY
from sqlalchemy.sql import func, select, insert
from sqlalchemy.exc import IntegrityError

logging.basicConfig(filename='load_sessions.log',level=logging.INFO)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres://localhost/accelerator')
engine = sqlalchemy.create_engine(DATABASE_URL)
metadata = MetaData()

search_table = Table('searches', metadata,
    Column('id', BigInteger, primary_key=True),
    Column('query_id', None, ForeignKey('queries.query_id')),
    Column('dataset_id', None, ForeignKey('datasets.dataset_id')),
    Column('clicked_urls', ARRAY(String)),
    Column('passed_over_urls', ARRAY(String)),
    Column('final_click_url', String),
    Column('final_click_rank', Integer)
)

query_table = Table('queries', metadata,
    Column('query_id', BigInteger, primary_key=True),
    Column('search_term_lowercase', String, unique=True),
)

dataset_table = Table('datasets', metadata,
    Column('dataset_id', BigInteger, primary_key=True),
    Column('filename', String),
    Column('latest_run', Boolean, default=True),
    Column('date_loaded', Date, server_default=func.now()),
)


def sessions_to_observations(df):
    """
    Map from sessionId to a list of all indexes relating to that session
    """
    sessions = defaultdict(list)
    for index, row in df.iterrows():
        session = row['searchSessionId']
        sessions[session].append(index)

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
    logging.info(f'passed over: {passed_over_results}')
    logging.info(f'clicked: {clicked_results}')
    logging.info(f'final rank: {final_rank}')

    return {
        'searchSessionId': session_id,
        'searchTerm': search_term,
        'finalRank': final_rank.item(),
        'passedOverResults': passed_over_results,
        'clickedResults': clicked_results,
        'finalItemClicked': final_url_clicked,
    }


def update_previous_runs(conn, input_filename):
    """
    Mark data from previous runs of this file (it can probably be deleted)
    """
    stmt = dataset_table.update().values(latest_run=False).where(dataset_table.c.filename == input_filename)
    result = conn.execute(stmt)
    logging.info(f'Marked {result.rowcount} previous versions of this dataset as outdated')


def insert_session_into_database(search_session, conn, input_filename):
    """
    Load a session summary into the database
    """
    try:
        stmt = query_table.insert().values(search_term_lowercase=search_session['searchTerm'])
        result = conn.execute(stmt)
        query_id = result.inserted_primary_key[0]
    except IntegrityError:
        stmt = select([query_table.c.query_id])
        result = conn.execute(stmt)
        query_id = result.fetchone()[0]

    stmt = dataset_table.insert().values(filename=input_filename)
    result = conn.execute(stmt)
    dataset_id = result.inserted_primary_key[0]

    stmt = search_table.insert().values(
        query_id=query_id,
        dataset_id=dataset_id,
        clicked_urls=search_session['clickedResults'],
        passed_over_urls=search_session['passedOverResults'],
        final_click_url=search_session['finalItemClicked'],
        final_click_rank=search_session['finalRank']
    )
    result = conn.execute(stmt)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python group_session_clicks_from_api_data.py [input csv]')
        sys.exit(1)

    print('Setting up database...')
    metadata.create_all(engine)
    conn = engine.connect()

    input_filename = sys.argv[1]

    df = pd.read_csv(input_filename)

    print('Updating metadata for previous runs...')
    update_previous_runs(conn, input_filename)

    print('Creating session map...')
    session_map = sessions_to_observations(df)

    print('Processing sessions...')
    invalid_counter = Counter()
    for session_id in session_map:
        logging.info(session_id)
        session_df = session_data(df, session_map, session_id)
        session_summary = process_session(session_df, invalid_counter=invalid_counter)

        if session_summary is None:
            continue

        try:
            insert_session_into_database(session_summary, conn, input_filename)
        except Exception:
            logging.exception('Unable to insert into database: {session_summary}')
            invalid_counter['database_errors'] += 1

    print(f'Invalid sessions: {invalid_counter}')