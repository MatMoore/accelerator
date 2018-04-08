import pandas as pd
import sys
import os
from collections import defaultdict
import logging

logging.basicConfig(filename='group_session_clicks_from_api_data.log',level=logging.INFO)


def sessions_to_observations(df):
    """
    Map from sessionId to a list of all indexes relating to that session
    """
    print('Creating session map...')

    sessions = defaultdict(list)
    for index, row in df.iterrows():
        session = row['searchSessionId']
        sessions[session].append(index)

    print('Done')

    return sessions


def process_session(input_data, session_map, session_id, result_data):
    indexes = session_map[session_id]

    rank_order = input_data.loc[indexes].sort_values(by=['rank'], ascending=False)
    clicks = rank_order[rank_order.clicks > 0]

    if not len(clicks):
        # Discard session if no clicks on first page
        return result_data

    row = clicks.iloc[0]

    search_term = row['searchTerm']
    final_url_clicked = row['contentIdOrPath']
    final_rank = row['rank']

    unclicked = rank_order[(rank_order.clicks == 0) & (rank_order.loc[:, 'rank'] < final_rank)]

    unclicked_results = unclicked.contentIdOrPath.str.cat(sep='|')
    clicked_results = clicks.contentIdOrPath.str.cat(sep='|')
    logging.info(f'unclicked: {unclicked_results}')
    logging.info(f'clicked: {clicked_results}')

    return result_data.append({
        'searchSessionId': session_id,
        'searchTerm': search_term,
        'finalRank': final_rank,
        'unclickedResults': unclicked_results,
        'clickedResults': clicked_results,
        'finalItemClicked': final_url_clicked,
    }, ignore_index=True)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python group_session_clicks_from_api_data.py [input csv] [output csv]')
        sys.exit(1)

    df = pd.read_csv(sys.argv[1])
    session_map = sessions_to_observations(df)

    results = pd.DataFrame(columns=['searchSessionId', 'searchTerm', 'finalItemClicked', 'finalRank'])

    print('Processing sessions...')
    for session_id in session_map:
        logging.info(session_id)
        results = process_session(input_data=df, session_id=session_id, session_map=session_map, result_data=results)

    results.to_csv(sys.argv[2], index=False)