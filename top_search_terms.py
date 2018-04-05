"""
Get the top 100 search terms from GA
"""
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from os import environ
import pandas as pd
import googleapiclient.errors
import time
import ga


def top_search_terms(analytics):
    """
    Get the top searches by number of clicks since June 2017, when we switched on Enhanced-Ecommerce.

    Use number of clicks on first page rather than number of searches.
    This will weight things towards queries with a lot of clicks,
    but I need a high number of clicks to infer anything about the optimal ranking.
    """
    request_body =  {
        'viewId': ga.VIEW_ID,
        'dateRanges': [{'startDate': '2017-07-01', 'endDate': '2018-04-01'}],
        'metrics': [{'expression': ga.LINK_CLICKS}],
        'orderBys': [{'fieldName': ga.LINK_CLICKS, 'sortOrder': 'DESCENDING'}],
        'dimensions': [{'name': ga.CUSTOM_VARIABLE_SEARCH_QUERY}],

        'dimensionFilterClauses': [{
            'operator': 'AND',
            'filters': [
                {
                    "dimensionName": ga.LINK_POSITION,
                    "operator": "NUMERIC_LESS_THAN",
                    "expressions": ["21"]
                },
                {
                    "dimensionName": "ga:productListName",
                    "operator": "EXACT",
                    "expressions": ["Site search results"]
                }
            ]
        }]
    }

    return analytics.reports().batchGet(
        body={
            'reportRequests': [
              request_body
            ],
            'useResourceQuotas': True,
        }
   ).execute()


if __name__ == '__main__':
    analytics = ga.initialize_analyticsreporting()
    results = top_search_terms(analytics)
    df = ga.page_to_dataframe(results)
    df = df.rename({'ga:dimension71': 'searchTerm', 'ga:productListClicks': 'clicks'}, axis='columns')

    df = df[df.searchTerm != '爱奇艺'] # spam?

    df['searchTerm'] = df['searchTerm'].map(lambda x: x.strip())

    df.to_csv('data/top_searches.csv', index=False)

    for term in df.searchTerm:
        print(term)