import sys
import time

from pyclick.click_models.Evaluation import LogLikelihood, Perplexity
from pyclick.click_models.DBN import DBN
from pyclick.click_models.SDBN import SDBN
from pyclick.utils.Utils import Utils
from pyclick.click_models.task_centric.TaskCentricSearchSession import TaskCentricSearchSession
from pyclick.search_session.SearchResult import SearchResult

from database import setup_database, get_searches, get_clicked_urls, get_passed_over_urls


def get_sessions():
    # session = TaskCentricSearchSession(task, query)
    # result = SearchResult(_result, 0)
    # session.web_results.append(result)
    # session.web_results[-1].click = 1
    return []


if __name__ == "__main__":
    click_model = SDBN()

    search_sessions = get_sessions()
    train_test_split = int(len(search_sessions) * 0.75)
    train_sessions = search_sessions[:train_test_split]
    train_queries = Utils.get_unique_queries(train_sessions)

    test_sessions = Utils.filter_sessions(search_sessions[train_test_split:], train_queries)
    test_queries = Utils.get_unique_queries(test_sessions)

    print("===============================")
    print("Training on %d search sessions (%d unique queries)." % (len(train_sessions), len(train_queries)))
    print("===============================")

    start = time.time()
    click_model.train(train_sessions)
    end = time.time()
    print("\tTrained %s click model in %i secs:\n%r" % (click_model.__class__.__name__, end - start, click_model))

    print("-------------------------------")
    print("Testing on %d search sessions (%d unique queries)." % (len(test_sessions), len(test_queries)))
    print("-------------------------------")

    loglikelihood = LogLikelihood()
    perplexity = Perplexity()

    start = time.time()
    ll_value = loglikelihood.evaluate(click_model, test_sessions)
    end = time.time()
    print("\tlog-likelihood: %f; time: %i secs" % (ll_value, end - start))

    start = time.time()
    perp_value = perplexity.evaluate(click_model, test_sessions)[0]
    end = time.time()
    print("\tperplexity: %f; time: %i secs" % (perp_value, end - start))
