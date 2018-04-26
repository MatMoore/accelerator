import numpy as np

def counterexample(fn):
    def wrapper(df, *args, **kwargs):
        matches = fn(df, *args, **kwargs)
        if sum(matches) == 0:
            return
        else:
            print(f'Failed check {fn.__name__} with {args}')
            print(df[matches].head())
            raise AssertionError(f'Failed {fn.__name__}')
    return wrapper

@counterexample
def complete(df, col):
    return df[col].isna() | df[col].apply(np.isinf)

@counterexample
def less_than_column(df, col1, col2):
    return df[col1] >= df[col2]

@counterexample
def less_than_or_equal_to_column(df, col1, col2):
    return df[col1] > df[col2]

@counterexample
def within_range(df, col1, lower, upper):
    return (df[col1] < lower) | (df[col1] > upper)

# Compare row sizes

# assert has min rows

# column headings

# unique values

class SeriesProperties:
    def __init__(self, df, col):
        self.df = df
        self.col = col

    def complete(self):
        complete(self.df, self.col)
        return self

    def less_than_column(self, col2):
        less_than_column(self.df, self.col, col2)
        return self

    def less_than_or_equal_to_column(self, col2):
        less_than_or_equal_to_column(self.df, self.col, col2)
        return self

    def within_range(self, lower, upper):
        within_range(self.df, self.col, lower, upper)