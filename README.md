# Modelling user behaviour to benchmark GOV.UK's search engine
This repository contains code and a blog for my data science accelerator project (https://matmoore.github.io/accelerator/)

## Overview
This was a 3 month project to mine search logs for evaluating/improving the search function on [GOV.UK](https://www.gov.uk). I worked on this project 1 day a week from April to June 2018.

More background:
- [About the project](https://matmoore.github.io/accelerator/post/what-is-this/)
- [How does GOV.UK search work at the moment](https://matmoore.github.io/accelerator/post/background-govuk-search/)
- [Predicting search result relevance with a click model](https://matmoore.github.io/accelerator/post/dynamic-bayesian-network-model/)

### Data
For every search session I store these things:

|Variable|Format|Purpose|
|--|--|--|
| searchTerm | String | What the user typed into the search bar |
| finalItemClicked | UUID or URL | ID of the last thing clicked |
| finalRank | Integer | Rank of the last thing clicked |
| clickedResults | Array of UUIDs or URLs | IDs of everything clicked in the session |
| allResults | Array of UUIDs or URLs| IDs of everything displayed on a search result page |

I defined a search session to be a user viewing a distinct search query within a single visit to GOV.UK. So if they return to the same search multiple times, it's still considered the same session, no matter what pages they
visited in the middle.

## Running the code in this repository

### Dependencies
To run this code you need access to the GOV.UK Google Analytics BigQuery export, and a relational database to write data to.

You need to configure the following environment variables:

|Variable|Format|Purpose|Default|
|--|--|--|--|
| DATABASE_URL | String | which local database to use |postgres://localhost/accelerator|
| BIGQUERY_PRIVATE_KEY_ID | String | Key id from bigquery credentials ||
| BIGQUERY_PRIVATE_KEY | SSH key | SSH key from bigquery credentials ||
| BIGQUERY_CLIENT_EMAIL | Email address | Client email from bigquery credentials ||
| BIGQUERY_CLIENT_ID | String| Client ID from bigquery credentials ||
| DEBUG | String| If set to anything, debug the code using part of the dataset ||

These can be set in a `.env` file for local development when using pipenv.

### Running the ETL pipeline
The following scripts form a pipeline to extract, transform and load the data into a database:
- `pipenv run python bigquery.py` exports session data from google query
- `pipenv run clean_data_from_bigquery.py [PATH_TO_RAW_DATA] [OUTPUT_PATH]` cleans up the output of `bigquery.py` and produces a single dataset where each row is a unique combination of (session, query, document)
- `pipenv run load_sessions.py [INPUT_FILE]` groups the data by session and imports it into a local database

Some of these scripts use hardcoded dates and filenames, so check the code before running them.

After running these you will have the following tables, arranged as a [STAR schema](https://en.wikipedia.org/wiki/Star_schema):
- `searches` - observations, where each row is a search session
- `queries` - each row is a unique search query
- `datasets` - each row records metadata about a single run of the `load_sessions.py` script. This is for debugging purposes only.

Once the data is loaded, I manually ran a SQL query to mark queries as high volume or low volume.
This is a separate step because I ended up loading the data in batches, and I could consider more
queries high volume if I collected more data.

```sql
with foo as (select query_id from queries join searches using (query_id) group by query_id having count(*) > 1000) update queries set high_volume=true from foo where queries.query_id=foo.query_id;
```

### Training a click model
To train the click model, first run `pipenv run split_data.py` to create training/test datasets. You need to have run all the previous steps first. This will output CSV files with the test and training datasets.

Then run `pipenv run python estimate_with_pyclick.py`. This uses a Simplified Dynamic Bayesian Network model, which should be very fast (a few minutes on my Macbook pro). In contrast, the full Dynamic Bayesian network model takes hours rather than minutes. If you want to speed it up you can try using PyPy as recommended by PyClick, but I didn't get this working.

### Evaluating the click model's inferred optimal ranking
The trained click model can be used to rerank a set of search results so that the most "relevant" results
are at the top. I compared to this the ranking the user originally saw, by looking at whether their
chosen result moved up or down.

The script I used to do this is `evaluate_model.py`.

Unfortunately this metric is biased towards results that were originally ranked higher up, but I didn't
come up with a better one in the time I had.