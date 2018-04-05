from google.cloud import bigquery
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from os import environ

# this works but returns a low level API client
# documentation: https://developers.google.com/api-client-library/python/guide/aaa_apikeys
# key = environ['BIGQUERY_API_KEY']
# service = build('bigquery', 'v2', developerKey=key)

SCOPES = ['https://www.googleapis.com/auth/bigquery'] # https://developers.google.com/identity/protocols/googlescopes#bigqueryv2]

client = bigquery.Client.from_service_account_json('bigquery_keys.json')

query = '''
SELECT
  CONCAT(
    'https://stackoverflow.com/questions/',
    CAST(id as STRING)) as url,
  view_count
FROM `bigquery-public-data.stackoverflow.posts_questions`
WHERE tags like '%google-bigquery%'
ORDER BY view_count DESC
LIMIT 10
'''

query2 = '''
SELECT
fullVisitorId
FROM
`govuk-bigquery-analytics.87773428.ga_sessions_20180403`
LIMIT 10
'''

query_job = client.query(query2)
results = query_job.result()

for row in results:
    print(row.fullVisitorId)

import pdb; pdb.set_trace()