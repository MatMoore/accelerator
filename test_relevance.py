import pandas as pd
import pytest
from estimate_relevance import SimplifiedDBNModel, ModelTester


example_search = pd.DataFrame(
    {
        'final_click_url': ['a', 'c', 'a', 'b', 'c'],
        'clicked_urls': [['a'], ['c'], ['a'], ['a', 'b'], ['b', 'c']],
        'skipped_urls': [[], ['a', 'b'], [], [], ['a']],
        'final_click_rank': [1, 3, 1, 2, 3],
        'search_term_lowercase': ['foo'] * 5
    },
    index=[1, 2, 3, 4, 5]
)


def test_attractiveness_ratio():
    model = SimplifiedDBNModel()
    model.train(example_search)

    assert model.document_params.attractiveness['foo']['a'] == 0.6
    assert model.document_params.attractiveness['foo']['b'] == 2/3
    assert model.document_params.attractiveness['foo']['c'] == 1


def test_satisfyingness_ratio():
    model = SimplifiedDBNModel()
    model.train(example_search)

    assert model.document_params.satisfyingness['foo']['a'] == 2/3
    assert model.document_params.satisfyingness['foo']['b'] == 0.5
    assert model.document_params.satisfyingness['foo']['c'] == 1


def test_error_of_barely_seen_hit():
    model = SimplifiedDBNModel()
    model.train(example_search)

    assert model.document_params.clicked['foo']['c'] == 2
    assert model.document_params.clicked_error['foo']['c'] == 2**0.5

    assert model.document_params.skipped['foo']['c'] == 0
    assert model.document_params.skipped_error['foo']['c'] == 0

    assert model.document_params.examined['foo']['c'] == 2
    assert model.document_params.examined_error['foo']['c'] == 2**0.5

    cov = model.document_params.cov_clicked_examined['foo']['c']
    assert model.document_params.attractiveness['foo']['c'] == 1

    rel1 = 2**0.5/2
    rel2 = 2**0.5/2
    rel_cov = cov/4
    expected_error = 1 * (rel1 ** 2 + rel2 ** 2 - 2 * rel_cov) ** 0.5
    assert model.document_params.attractiveness_error['foo']['c'] == expected_error


class DummyRanker:
    def __init__(self, new_rank):
        self.new_rank = new_rank

    def rank(self, query):
        return pd.Series(self.new_rank)


def test_positive_change_in_rank():
    # Move C from 3rd to 1st
    tester = ModelTester(DummyRanker({'a': 3, 'b': 2, 'c': 1}))

    test_row = pd.Series(
        {
            'final_click_url': 'c',
            'clicked_urls': ['b', 'c'],
            'final_click_rank': 3,
            'search_term_lowercase': 'foo'
        }
    )

    assert tester.change_in_rank_of_preferred_document(test_row) == 2

def test_negative_change_in_rank():
    # Move A from 1st to 3rd
    tester = ModelTester(DummyRanker({'a': 3, 'b': 2, 'c': 1}))

    test_row = pd.Series(
        {
            'final_click_url': 'a',
            'clicked_urls': ['b', 'c'],
            'final_click_rank': 1,
            'search_term_lowercase': 'foo'
        }
    )

    assert tester.change_in_rank_of_preferred_document(test_row) == -2