# accelerator
Code for my data science accelerator project (https://matmoore.github.io/accelerator/)

## Session dataset
The basic dataset I'm trying to generate has these columns:

|Column|Format|Purpose|
|--|--|--|
|searchSessionId | String | Uniquely identify a combination of user + search query |
| searchTerm | String | What the user typed into the search bar |
| finalItemClicked | UUID or URL | ID of the last thing clicked |
| finalRank | Integer | Rank of the last thing clicked |
| clickedResults | Pipe separated string | IDs of everything clicked in the session |
| unclickedResults | Pipe seperated string | IDs of everything above the last clicked item that wasn't clicked |

## Scripts
The following scripts produce a dataset using the google analytics API:
- `pipenv run python ga.py` fetches data 1000 rows at a time and writes each page to a CSV file
- `pipenv run clean_data_from_api.py [PATH_TO_RAW_DATA] [OUTPUT_PATH]` cleans up the output of `ga.py` and produces a single dataset where each row is a unique combination of (session, query, document)
- `pipenv run group_session_clicks_from_api_data.py [INPUT_FILE] [OUTPUT_FILE]` groups the data by session and filters out sessions with no clicks

Other scripts:
- `pipenv run python bigquery.py` fetches data from bigquery (not working yet - see `queries/` for the queries themselves)
- `pipenv run top_search_terms.py` uses the google analytics API to fetch the top queries, based on the number of clicks on results

## Queries
The sql in `queries/` is intended to be run against the [Google BigQuery export of the analytics data](https://support.google.com/analytics/answer/3437719?hl=en).

- `search_sessions.sql` produces similar data to `ga.py`
- `sequences.sql` looks at all the pages a user visits after running a search (this is not used)
