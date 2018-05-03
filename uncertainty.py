"""
Formulas for propagating uncertainty

https://en.wikipedia.org/wiki/Propagation_of_uncertainty#Example_formulas
"""
import numpy as np

def sum_error(a_err, b_err, covariance):
    """
    Absolute error of a sum of two values
    """
    variance = a_err.pow(2) + b_err.pow(2) + 2 * covariance
    return variance.pow(1/2)

def ratio_relative_error(num, den, num_err, den_err, covariance):
    """
    Relative error of a ratio
    """
    num_term = num_err.divide(num).replace(np.inf, 0).fillna(0).pow(2)
    den_term = den_err.divide(den).replace(np.inf, 0).fillna(0).pow(2)
    covariance_term = 2 * covariance.divide(num * den).replace(np.inf, 0).fillna(0)
    variance = num_term + den_term - covariance_term
    return variance.pow(1/2)


def product_relative_error(a, b, a_err, b_err, covariance):
    """
    Relative error of a product of two values
    If either a or b are zero, their contributions to the error will be zero
    """
    a_term = a_err.divide(a).replace(np.inf, 0).fillna(0).pow(2)
    b_term = b_err.divide(b).replace(np.inf, 0).fillna(0).pow(2)
    covariance_term = 2 * covariance.divide(a * b).replace(np.inf, 0).fillna(0)

    variance = a_term + b_term + covariance_term
    return variance.pow(1/2)