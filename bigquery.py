from google.cloud import bigquery
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from os import environ

SCOPES = ['https://www.googleapis.com/auth/bigquery'] # https://developers.google.com/identity/protocols/googlescopes#bigqueryv2]

client = bigquery.Client.from_service_account_json('govuk_bigquery.json')

# There are ~100,000 sessions involving search per day
# and the estimated results size is around 1GB per week of data
# TODO: measure the actual size
query = '''
SELECT
CONCAT(fullVisitorId,'|',CAST(visitId as STRING)) AS sessionId,
customDimensions.value as searchTerm,
hits.hitNumber as hitNumber, -- This is the hit number of the results page (for impressions) or the page itself (for clicks)
product.productSKU as contentIdOrPath,
product.productListPosition as linkPosition,
CASE
    WHEN product.isImpression = true and product.isClick IS NULL THEN 'impression'
    WHEN product.isClick = true and product.isImpression IS NULL THEN 'click'
    ELSE NULL
END AS observationType

FROM `govuk-bigquery-analytics.87773428.ga_sessions_*`
CROSS JOIN UNNEST(hits) as hits
CROSS JOIN UNNEST(hits.product) as product
CROSS JOIN UNNEST(product.customDimensions) as customDimensions

WHERE product.productListName = 'Site search results'
AND _TABLE_SUFFIX BETWEEN '20180403' AND '20180403'
AND product.productListPosition <= 20
AND customDimensions.index = 71
LIMIT 10
'''

# Bigquery client docs: https://googlecloudplatform.github.io/google-cloud-python/latest/bigquery/usage.html
query_job = client.query(query)
results = query_job.result()

for row in results:
  print(row)