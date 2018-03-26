"""
Some hacky code to interact with the google analytics API

Based on the example code here:
https://developers.google.com/analytics/devguides/reporting/core/v4/quickstart/service-py
"""
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from os import environ
import pandas as pd

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
VIEW_ID = '56562468'  # Q. Site search (entire site with query strings)
# VIEW_ID = '53872948' # 1a. GOV.UK - Main profile
GOOGLE_CLIENT_EMAIL = environ['GOOGLE_CLIENT_EMAIL']
GOOGLE_PRIVATE_KEY = environ['GOOGLE_PRIVATE_KEY']

# Constants for dimensions, metrics, variables
# https://developers.google.com/analytics/devguides/reporting/core/dimsmets lists everything that's available.
CUSTOM_VARIABLE_SEARCH_QUERY = 'ga:dimension71' # The user's search term
LINK_IMPRESSIONS = 'ga:productListViews'        # Number of times the link appeared in search results
LINK_CLICKS = 'ga:productListClicks'            # Number of times the user clicked the link when it appeared in search results
LINK_CTR = 'ga:productListCTR'                  # ga:productListClicks / ga:productListViews
LINK_POSITION = 'ga:productListPosition'        # the position the link appeared in the search results
CONTENT_ID_OR_PATH = 'ga:productSku'            # the content ID of the link if available, else the path
CLIENT_ID = 'ga:dimension95'                    # the GA client ID

def initialize_analyticsreporting():
    """Initializes an Analytics Reporting API V4 service object.

    Returns:
    An authorized Analytics Reporting API V4 service object.
    """

    parsed_keyfile = {
        'type': 'service_account',
        'client_email': GOOGLE_CLIENT_EMAIL,
        'private_key': GOOGLE_PRIVATE_KEY,
        'private_key_id': None,
        'client_id': None
    }

    credentials = ServiceAccountCredentials._from_parsed_json_keyfile(
        parsed_keyfile,
        scopes=SCOPES
    )

    # Build the service object.
    analytics = build('analyticsreporting', 'v4', credentials=credentials)

    return analytics


def old_clicks_with_positions(analytics):
    """
    This fetches search clicks with position using the old cookie tracking
    method.

    The position of the link in search results was propagated via a cookie and
    set as a custom dimension when the page was viewed.

    This gives us number of clicks for each combination of (query, content item, position)

    This query is based on https://github.com/gds-attic/search-performance-dashboard/blob/master/dashboard/fetch/ga.py

    FIXME: this does not return any results
    """

    return analytics.reports().batchGet(
        body={
            'reportRequests': [
                {
                    'viewId': VIEW_ID,
                    'dateRanges': [{'startDate': '2017-01-01', 'endDate': '2017-01-03'}],
                    'metrics': [{'expression': 'ga:pageViews'}],
                    #'orderBys': [{'fieldName': 'ga:pageViews', 'sortOrder': 'DESCENDING'}],
                    'dimensions': [{'name': 'ga:pagePath'}, {'name': 'ga:previousPagePath'}, {'name': 'ga:customVarValue21'}],
                    'dimensionFilterClauses': [{
                        'operator': 'AND',
                        'filters': [
                            {
                                "dimensionName": "ga:previousPagePath",
                                "operator": "REGEXP",
                                "expressions": [r'^/search\?']
                            },
                            # {
                            #     "dimensionName": "ga:pagePath",
                            #     "operator": "REGEXP",
                            #     "not": True,
                            #     "expressions": [r'^/search\?']
                            # },
                            # {
                            #     "dimensionName": "ga:customVarValue21",
                            #     "operator": "REGEXP",
                            #     "expressions": [r'.']
                            # },
                        ]
                    }],
                }]
        }
    ).execute()


def clicks_with_positions(analytics, next_page_token=None):
    """
    Get number of clicks on search results with positions.

    We send the position of the result with each click and impression using Enhanced-Ecommerce
    """
    request_body =  {
        'viewId': VIEW_ID,
        'dateRanges': [{'startDate': '2018-01-01', 'endDate': '2018-01-01'}],
        'metrics': [{'expression': LINK_CTR}, {'expression': LINK_IMPRESSIONS}, {'expression': LINK_CLICKS}],
        #'orderBys': [{'fieldName': 'ga:pageViews', 'sortOrder': 'DESCENDING'}],
        #'dimensions': [{'name': CLIENT_ID}, {'name': CONTENT_ID_OR_PATH}, {'name': LINK_POSITION}, {'name': CUSTOM_VARIABLE_SEARCH_QUERY}],
        'dimensions': [{'name': 'ga:hour'}, {'name': CLIENT_ID}, {'name': CONTENT_ID_OR_PATH}, {'name': LINK_POSITION}, {'name': CUSTOM_VARIABLE_SEARCH_QUERY}],

        'dimensionFilterClauses': [{
            'operator': 'AND',
            'filters': [
                {
                    "dimensionName": LINK_POSITION,
                    "operator": "NUMERIC_LESS_THAN",
                    "expressions": ["21"]
                },
                {
                    "dimensionName": "ga:productListName",
                    "operator": "EXACT",
                    "expressions": ["Site search results"]
                },
                {
                    "dimensionName": "ga:hour",
                    "operator": "EXACT",
                    "expressions": ["09"]
                },
            ]
        }]
    }

    if next_page_token:
      request_body['nextPageToken'] = next_page_token

    return analytics.reports().batchGet(
        body={
            'reportRequests': [
              request_body
            ],
            'useResourceQuotas': True,
        }
   ).execute()


def extract_page_token(response):
  try:
    return response['reports'][0]['nextPageToken']
  except KeyError:
    return None


def get_report(analytics):
    """Queries the Analytics Reporting API V4.

    Args:
      analytics: An authorized Analytics Reporting API V4 service object.
    Returns:
      The Analytics Reporting API V4 response.
    """
    return analytics.reports().batchGet(
        body={
            'reportRequests': [
                {
                    'viewId': VIEW_ID,
                    'dateRanges': [{'startDate': '7daysAgo', 'endDate': 'today'}],
                    'metrics': [{'expression': 'ga:sessions'}],
                    'dimensions': [{'name': 'ga:country'}]
                }]
        }
    ).execute()


def print_response(response):
    """Parses and prints the Analytics Reporting API V4 response.

    Args:
      response: An Analytics Reporting API V4 response.
    """
    for report in response.get('reports', []):
        columnHeader = report.get('columnHeader', {})
        dimensionHeaders = columnHeader.get('dimensions', [])
        metricHeaders = columnHeader.get(
            'metricHeader', {}).get('metricHeaderEntries', [])

        for row in report.get('data', {}).get('rows', []):
            dimensions = row.get('dimensions', [])
            dateRangeValues = row.get('metrics', [])

            for header, dimension in zip(dimensionHeaders, dimensions):
                print(header + ': ' + dimension)

            for i, values in enumerate(dateRangeValues):
                print('Date range: ' + str(i))
                for metricHeader, value in zip(metricHeaders, values.get('values')):
                    print(metricHeader.get('name') + ': ' + value)

def write_page_to_csv(response, filename):
  report = response['reports'][0]

  #assert report['isDataGolden']

  columnHeader = report.get('columnHeader', {})
  dimensionHeaders = columnHeader.get('dimensions', [])
  metricHeaders = columnHeader.get(
    'metricHeader', {}
  ).get('metricHeaderEntries', [])

  cols = dimensionHeaders + [h['name'] for h in metricHeaders]

  data = report['data']
  
  if 'samplesReadCounts' in data:
    print('Warning: Data is sampled!!')

  if not data['isDataGolden']:
    print('Warning: Data may change if requested later!!')

  rows = []
  for inrow in data['rows']:
    outrow = inrow['dimensions']
    metrics = inrow['metrics']
    assert len(metrics) == 1

    outrow.extend(metrics[0]['values'])

    rows.append(outrow)
  
  df = pd.DataFrame(rows, columns=cols)
  df.to_csv(filename)

  return df


def main():
    analytics = initialize_analyticsreporting()
    # response = get_report(analytics)
    # print_response(response)

    response = clicks_with_positions(analytics)
    print(response['reports'][0]['data']['totals'])
    print(response['reports'][0]['data']['rowCount'])
    query_cost = response['queryCost']
    print(f'Query cost {query_cost}')

    write_page_to_csv(response, 'data/clicks_with_positions_2018-01-01-0900_page-0001.csv')


if __name__ == '__main__':
    main()
