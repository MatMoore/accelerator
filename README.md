# accelerator
Code for my data science accelerator project (https://matmoore.github.io/accelerator/)

## Overview
This is a 3 month project to mine search logs for evaluating/improving the search function on [GOV.UK](https://www.gov.uk). I'm working on this project 1 day a week.

More background:
- [About the project](https://matmoore.github.io/accelerator/post/what-is-this/)
- [How does GOV.UK search work at the moment](https://matmoore.github.io/accelerator/post/background-govuk-search/)
- [Predicting search result relevance with a click model](https://matmoore.github.io/accelerator/post/dynamic-bayesian-network-model/)

## Data
For every search session I store these variables:

|Variable|Format|Purpose|
|--|--|--|
| searchTerm | String | What the user typed into the search bar |
| finalItemClicked | UUID or URL | ID of the last thing clicked |
| finalRank | Integer | Rank of the last thing clicked |
| clickedResults | Array of UUIDs or URLs | IDs of everything clicked in the session |
| unclickedResults | Array of UUIDs or URLs| IDs of everything above the last clicked item that wasn't clicked |

## Scripts
The following scripts need to be run in extract the data from bigquery, and load it into a local database:
- `pipenv run python bigquery.py` exports session data from google query
- `pipenv run clean_data_from_bigquery.py [PATH_TO_RAW_DATA] [OUTPUT_PATH]` cleans up the output of `bigquery.py` and produces a single dataset where each row is a unique combination of (session, query, document)
- `pipenv run load_sessions.py [INPUT_FILE]` groups the data by session and imports it into a local database

Other scripts:
`pipenv run python estimate_relevance.py` trains an SDBN model on the data

### Environment variables

These can be set in a `.env` file for local development.

|Variable|Format|Purpose|Default|
|--|--|--|--|
| DATABASE_URL | String | which local database to use |postgres://localhost/accelerator|
| BIGQUERY_PRIVATE_KEY_ID | String | Key id from bigquery credentials ||
| BIGQUERY_PRIVATE_KEY | SSH key | SSH key from bigquery credentials ||
| BIGQUERY_CLIENT_EMAIL | Email address | Client email from bigquery credentials ||
| BIGQUERY_CLIENT_ID | String| Client ID from bigquery credentials ||
| DEBUG | String| If set to anything, debug the code using part of the dataset ||