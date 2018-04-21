import pandas as pd
import pytest
from estimate_relevance import SimplifiedDBNModel

example_search = pd.DataFrame(
    {
        'final_click_url': ['a', 'c', 'a', 'b', 'c'],
        'clicked_urls': [['a'], ['c'], ['a'], ['a', 'b'], ['b', 'c']],
        'final_click_rank': [1, 3, 1, 2, 3],
        'search_term_lowercase': ['foo'] * 5
    },
    index=[1, 2, 3, 4, 5]
)

example_clicks = pd.DataFrame(
    {
        'result': ['a', 'c', 'a', 'a', 'b', 'b', 'c'],
        'search_term_lowercase': ['foo'] * 7
    },
    index=[1, 2, 3, 4, 4, 5, 5]
)

example_skips = pd.DataFrame(
    {
        'result': ['a', 'b', 'a'],
        'search_term_lowercase': ['foo'] * 3
    },
    index=[2, 2, 5]
)


def test_attractiveness_ratio():
    model = SimplifiedDBNModel()
    model.train(example_search, example_clicks, example_skips)
    
    assert model.attractiveness['foo']['a'] == 0.6
    assert model.attractiveness['foo']['b'] == 2/3
    assert model.attractiveness['foo']['c'] == 1


def test_satisfyingness_ratio():
    model = SimplifiedDBNModel()
    model.train(example_search, example_clicks, example_skips)

    assert model.satisfyingness['foo']['a'] == 2/3
    assert model.satisfyingness['foo']['b'] == 0.5
    assert model.satisfyingness['foo']['c'] == 1