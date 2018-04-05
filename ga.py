"""
Some hacky code to interact with the google analytics API

Based on the example code here:
https://developers.google.com/analytics/devguides/reporting/core/v4/quickstart/service-py
"""
from apiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from os import environ
import pandas as pd
import googleapiclient.errors
import time

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
VIEW_ID = '56562468'  # Q. Site search (entire site with query strings)
# VIEW_ID = '53872948' # 1a. GOV.UK - Main profile
# VIEW_ID = '87773428' # <- this is what's in bigquery
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


def clicks_only(analytics, search_term, next_page_token=None):
    """
    Get number of clicks on search results.

    We send the position of the result with each click and impression using Enhanced-Ecommerce
    """
    request_body =  {
        'viewId': VIEW_ID,
        'dateRanges': [{'startDate': '2018-03-01', 'endDate': '2018-03-14'}],
        'metrics': [{'expression': LINK_CLICKS}],
        #'orderBys': [{'fieldName': 'ga:pageViews', 'sortOrder': 'DESCENDING'}],
        #'dimensions': [{'name': CLIENT_ID}, {'name': CONTENT_ID_OR_PATH}, {'name': LINK_POSITION}, {'name': CUSTOM_VARIABLE_SEARCH_QUERY}],
        'dimensions': [{'name': CLIENT_ID}, {'name': CONTENT_ID_OR_PATH}, {'name': LINK_POSITION}, {'name': CUSTOM_VARIABLE_SEARCH_QUERY}],

        'metricFilterClauses': [{
            'filters': [{
                'metricName': LINK_CLICKS,
                'operator': 'GREATER_THAN',
                'comparisonValue': "0"
            }]
        }],

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
                    "dimensionName": CUSTOM_VARIABLE_SEARCH_QUERY,
                    "operator": "REGEXP",
                    "expressions": [search_term]
                },
            ]
        }]
    }

    if next_page_token:
      print('Using pageToken')
      request_body['pageToken'] = next_page_token

    #request_body['pageSize'] = 10_000

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


def write_page_to_csv(response, filename, **csv_kwargs):
  df = page_to_dataframe(response)
  df.to_csv(filename, **csv_kwargs)
  return df


def page_to_dataframe(response):
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

  return df


def main():
    analytics = initialize_analyticsreporting()
    # response = get_report(analytics)
    # print_response(response)

    with open('top_searches.txt') as f:
        search_terms = f.readlines()

    for search_term in search_terms:
        search_term = search_term.strip()
        search_term_regex = f"^\s*{search_term}\s*$" # allow for some whitespace around the search term

        i = 0
        next_page_token=None

        while True:
            i += 1

            try:
                response = clicks_only(analytics, search_term_regex, next_page_token=next_page_token)
            except googleapiclient.errors.HttpError as e:
                print(e)
                i -= 1
                time.sleep(100)
                continue
            except Exception as e:
                print(e)
                i -= 1
                time.sleep(1)
                continue

            next_page_token = extract_page_token(response)

            row_count = response['reports'][0]['data']['rowCount']
            query_cost = response['queryCost']
            totals = response['reports'][0]['data']['totals']

            print(f'Page {i}')
            print(f'Search term={search_term}')
            print(f'Row count: {row_count}')
            print(f'Query cost {query_cost}')
            print(f'Totals: {totals}')

            write_page_to_csv(response, 'data/top_search_terms/clicks_only_2018-03-01_2018-03-14_{search_term}_page-{i:03d}.csv'.format(i=i, search_term=search_term.replace(" ", "_")))

            if next_page_token is None:
                print('Next page not found, stopping')
                break
            else:
                print(f'Next page token: {next_page_token}')

if __name__ == '__main__':
    main()
