from google.cloud import bigquery
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from os import environ
import pandas_gbq

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
AND _TABLE_SUFFIX BETWEEN '20180403' AND '20180411'
AND product.productListPosition <= 20
AND customDimensions.index = 71
'''

results = pandas_gbq.read_gbq(query, project_id='govuk-bigquery-analytics', private_key='govuk_bigquery.json', dialect='standard')
results.to_csv('data/bigquery_results_20180403_20180411.csv', index=False)