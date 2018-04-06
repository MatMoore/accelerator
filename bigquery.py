from google.cloud import bigquery
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from os import environ

import pandas_gbq

# this works but returns a low level API client
# documentation: https://developers.google.com/api-client-library/python/guide/aaa_apikeys
# key = environ['BIGQUERY_API_KEY']
# service = build('bigquery', 'v2', developerKey=key)

SCOPES = ['https://www.googleapis.com/auth/bigquery'] # https://developers.google.com/identity/protocols/googlescopes#bigqueryv2]

client = bigquery.Client.from_service_account_json('govuk_bigquery.json')

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

# query_job = client.query(query2)
# results = query_job.result()

# for row in results:
#     print(row.fullVisitorId)

#results = pandas_gbq.read_gbq('SELECT fullVisitorId FROM `govuk-bigquery-analytics.87773428.ga_sessions_2018040` LIMIT 10', project_id='govuk-bigquery-analytics', private_key='govuk_bigquery.json')
results = pandas_gbq.read_gbq('SELECT fullVisitorId FROM govuk-bigquery-analytics.87773428.ga_sessions_2018040 LIMIT 10', project_id='govuk-bigquery-analytics', private_key='govuk_bigquery.json')

import pdb; pdb.set_trace()