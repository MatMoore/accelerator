from uncertainty import sum_error, ratio_relative_error, product_relative_error
import pandas as pd

def test_independent_ratio():
    a = pd.Series([1])
    b = pd.Series([1])
    a_err = pd.Series([1])
    b_err = pd.Series([1])
    cov = pd.Series([0])
    err = ratio_relative_error(a, b, a_err, b_err, cov)
    assert err[0] == 2 ** 0.5

def test_dependent_ratio():
    a = pd.Series([1])
    b = pd.Series([1])
    a_err = pd.Series([1])
    b_err = pd.Series([1])
    cov = pd.Series([1])
    err = ratio_relative_error(a, b, a_err, b_err, cov)
    assert err[0] == 0


def test_dependent_ratio_2():
    a = pd.Series([1])
    b = pd.Series([2])
    f = a/b
    a_err = pd.Series([1])
    b_err = pd.Series([2**0.5])
    cov = pd.Series([2**0.5])
    err = ratio_relative_error(a, b, a_err, b_err, cov)
    assert err[0] == (1+0.5-4*2**0.5) ** 0.5