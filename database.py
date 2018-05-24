"""
A database for storing session summaries.
"""
import os
import logging
import sqlalchemy
from sqlalchemy import Table, Column, BigInteger, Integer, Boolean, String, Date, MetaData, ForeignKey, ARRAY
from sqlalchemy.sql import func, select, insert, except_
from sqlalchemy.exc import IntegrityError
import pandas as pd

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres://localhost/accelerator')
engine = sqlalchemy.create_engine(DATABASE_URL)
metadata = MetaData()

search_table = Table('searches', metadata,
    Column('id', BigInteger, primary_key=True),
    Column('query_id', None, ForeignKey('queries.query_id', ondelete='CASCADE')),
    Column('dataset_id', None, ForeignKey('datasets.dataset_id', ondelete='CASCADE')),
    Column('clicked_urls', ARRAY(String), nullable=False),
    Column('all_urls', ARRAY(String), nullable=False),
    Column('final_click_url', String, nullable=False),
    Column('final_click_rank', Integer, nullable=False)
)

query_table = Table('queries', metadata,
    Column('query_id', BigInteger, primary_key=True),
    Column('search_term_lowercase', String, unique=True, nullable=False),
    Column('high_volume', Boolean, default=False)
)

dataset_table = Table('datasets', metadata,
    Column('dataset_id', BigInteger, primary_key=True),
    Column('filename', String, nullable=False, unique=True),
    Column('date_loaded', Date, server_default=func.now()),
)

# Import this from the data warehouse
content_item_table = Table('content_items', metadata,
    Column('id', BigInteger, primary_key=True),
    Column('content_id', String, nullable=False),
    Column('base_path', String, nullable=False),
    Column('title', String, nullable=True),
)

def setup_database():
    """
    Ensure all tables exist and get a connection
    """
    metadata.create_all(engine)
    return engine.connect()


def record_dataset(conn, input_filename):
    """
    Create a record of the dataset we loaded from.
    Returns the ID of the inserted row.
    """
    stmt = dataset_table.insert().values(filename=input_filename)
    result = conn.execute(stmt)
    return result.inserted_primary_key[0]


def insert_session_into_database(search_session, conn, dataset_id):
    """
    Load a session summary into the database
    """
    try:
        stmt = query_table.insert().values(search_term_lowercase=search_session['searchTerm'])
        result = conn.execute(stmt)
        query_id = result.inserted_primary_key[0]
    except IntegrityError:
        stmt = select([query_table.c.query_id]).where(query_table.c.search_term_lowercase == search_session['searchTerm'])
        result = conn.execute(stmt)
        query_id = result.fetchone()[0]

    stmt = search_table.insert().values(
        query_id=query_id,
        dataset_id=dataset_id,
        clicked_urls=search_session['clickedResults'],
        all_urls=search_session['allResults'],
        final_click_url=search_session['finalItemClicked'],
        final_click_rank=search_session['finalRank']
    )
    conn.execute(stmt)


def get_searches(conn):
    """
    Get a dataframe containing every search and the final thing clicked
    """
    stmt = select(
        [
            search_table.c.id,
            search_table.c.final_click_url,
            search_table.c.final_click_rank,
            query_table.c.search_term_lowercase,

            # These are arrays
            search_table.c.all_urls,
            search_table.c.clicked_urls,
        ]
    ).select_from(
        search_table.join(query_table)
    ).where(query_table.c.high_volume == True)

    # with foo as (select query_id from queries join searches using (query_id) group by query_id having count(*) > 1000) update queries set high_volume=true from foo where queries.query_id=foo.query_id;

    df = pd.read_sql(stmt, conn, index_col='id')

    return df


def get_skipped_urls(conn):
    """
    Get every query/result pair where the result was skipped

    This is done by unnesting everything so we have (session, result, query) tuples,
    and then excluding any clicked tuples from the passed over tuples.
    It probably makes sense(?)
    """
    passed_over = select(
        [
            search_table.c.id,
            func.unnest(search_table.c.passed_over_urls).label('result'),
            query_table.c.search_term_lowercase,
        ]
    ).select_from(
        search_table.join(query_table)
    ).where(query_table.c.high_volume == True)

    clicked = clicked_urls_query()

    stmt = except_(passed_over, clicked)

    return pd.read_sql(stmt, conn, index_col='id')


def get_clicked_urls(conn):
    """
    Get every query/result pair where the result was clicked
    """
    stmt = clicked_urls_query()

    return pd.read_sql(stmt, conn, index_col='id')


def clicked_urls_query():
    return select(
        [
            search_table.c.id,
            func.unnest(search_table.c.clicked_urls).label('result'),
            query_table.c.search_term_lowercase,
        ]
    ).select_from(
        search_table.join(query_table)
    ).where(query_table.c.high_volume == True)


def get_content_items(conn):
    stmt = select(
        [
            content_item_table.c.content_id,
            content_item_table.c.base_path,
            content_item_table.c.title
        ]
    )

    return pd.read_sql(stmt, conn, index_col='content_id')


if __name__ == '__main__':
    setup_database()