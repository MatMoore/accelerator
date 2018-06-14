"""
Use PyClick to train a Simplified DBN model and a full DBN model
and compare the results of the two models
"""
from pyclick.click_models.Evaluation import LogLikelihood, Perplexity
from pyclick.click_models.DBN import DBN
from pyclick.click_models.SDBN import SDBN
from pyclick.utils.Utils import Utils
from pyclick.click_models.task_centric.TaskCentricSearchSession import TaskCentricSearchSession
from pyclick.search_session.SearchResult import SearchResult
from database import get_searches, setup_database
from split_data import train_test_split
import time
import logging
import pyclick.click_models.Evaluation
from collections import OrderedDict, Counter
import pandas as pd
from evaluate_model import ModelTester, QueryDocumentRanker

# Override constant for the page size: we show 20 results per page
# so start by evaluating all of these.
# TODO: Do we get worse results by incluuding the bottom 10 links?
pyclick.click_models.Evaluation.RANK_MAX = 20

sdbn_click_model = SDBN()
dbn_click_model = DBN()


def load_searches_from_db():
    conn = setup_database()
    return get_searches(conn)


def map_to_pyclick_format(searches):
    """
    Turn my dataframe into a format that can be processed by PyClick
    """
    sessions = []
    counter = Counter()

    for search in searches.itertuples():

        query = search.search_term_lowercase

        session = TaskCentricSearchSession(query, query)

        if len(search.all_urls) != 20:
            # When I load the data into the database I check that the *ranks* are complete from 1-20.
            # BUT this doesn't mean there are 20 impressions!
            # When a user navigates back and forth between the result page, impressions may be sent
            # again if the page is reloaded. In which case `all_results` will be a multiple of 20.
            # Additionally, if the results *change* between those page views, there will be more than
            # 20 unique links stored in all_urls.
            # My existing code sort of merges this into one uber result set, but PyClick crashes
            # if a session contains more URLs than RANK_MAX. So here we remove any duplicates and then
            # truncate to 20 links.
            unique_links = list(OrderedDict((k, k) for k in search.all_urls).keys())
            counter['truncated_urls'] += 1
        else:
            unique_links = search.all_urls
            counter['ok_urls'] += 1

        for url in unique_links[:20]:
            if query == 'apprenticeships' and url == '45ad868a-2e79-4029-991b-c29559d7eb29':
                print('.', end='')

            if url in search.clicked_urls:
                result = SearchResult(url, 1)
            else:
                result = SearchResult(url, 0)
            session.web_results.append(result)

        sessions.append(session)


    print(counter)

    return sessions


def train_model(model, train_sessions, train_queries):
    print("===============================")
    print("Training on %d search sessions (%d unique queries)." % (len(train_sessions), len(train_queries)))
    print("===============================")
    start = time.time()
    model.train(train_sessions)
    print(sdbn_click_model.params[sdbn_click_model.param_names.attr].get('apprenticeships', '45ad868a-2e79-4029-991b-c29559d7eb29')._denominator)
    end = time.time()
    print("\tTrained %s click model in %i secs:\n%r" % (model.__class__.__name__, end - start, model))


def evaluate_fit(trained_model, test_sessions, test_queries):
    """
    Evaluate the model's fit to the observed data - i.e. whether C==0 or C==1 for every
    item/session.

    There are two measures:

    - Log likelihood goes from negative infinity (bad) to 0 (good)
    - It measures the likelihood of observing the clicks in all the test sessions if the model is correct
    - Perplexity goes from 1 (good) to 2 (bad).
    - It's a measure of how surprised we are about all clicks and non-clicks in all of the test sessions if the model is correct.
    - When comparing models you can use perplexity gain (pB - pA) / (pB - 1)
    - It can be computed at individual ranks, or averaged across all ranks. Perplexity is normally higher for higher ranks.
    """
    print("-------------------------------")
    print("Testing on %d search sessions (%d unique queries)." % (len(test_sessions), len(test_queries)))
    print("-------------------------------")

    loglikelihood = LogLikelihood()
    perplexity = Perplexity()

    start = time.time()
    ll_value = loglikelihood.evaluate(trained_model, test_sessions)
    end = time.time()
    print("\tlog-likelihood: %f; time: %i secs" % (ll_value, end - start))

    start = time.time()
    perp_value = perplexity.evaluate(trained_model, test_sessions)[0]
    end = time.time()
    print("\tperplexity: %f; time: %i secs" % (perp_value, end - start))


if __name__ == "__main__":
    logging.basicConfig(filename='estimate_with_pyclick.log',level=logging.INFO)

    searches = load_searches_from_db()
    training, test = train_test_split(searches)
    train_sessions = map_to_pyclick_format(training)
    test_sessions = map_to_pyclick_format(test)
    train_queries = Utils.get_unique_queries(train_sessions)

    # PyClick normally filters out any test sessions that aren't in the training set.
    # I shouldn't need to do this, because my train/test split shouldn't let this happen.
    assert len(test_sessions) == len(Utils.filter_sessions(test_sessions, train_queries))

    test_queries = Utils.get_unique_queries(test_sessions)

    print('SDBN')
    train_model(sdbn_click_model, train_sessions, train_queries)
    evaluate_fit(sdbn_click_model, test_sessions, test_queries)

    with open('sdbn_model2.json', 'w') as f:
        f.write(sdbn_click_model.to_json())

    from evaluate_model import PyClickModelAdapter, QueryDocumentRanker

    ranker = QueryDocumentRanker(PyClickModelAdapter(sdbn_click_model))
    tester = ModelTester(ranker)
    evaluation = tester.evaluate(test)

    print(f'Mean change in rank: {evaluation.change_in_rank.mean()}')
    print(f'Mean saved clicks: {evaluation.saved_clicks.mean()}')

    import pdb; pdb.set_trace()