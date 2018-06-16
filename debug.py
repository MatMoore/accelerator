"""
Debug models and evaluation code

What results will my evaluation metric value?

"""
from split_data import load_from_csv
from database import get_content_items, setup_database


def expand_content_ids(df, on=None):
    conn = setup_database()
    content_items = get_content_items(conn)
    return df.join(content_items, how='left', on=on)


if __name__ == '__main__':
    # Subset of queries I'm using to debug stuff
    eyeball_queries = ['apprenticeships', 'self assessment', 'land registry', 'child benefit', 'visa', 'tax credit', 'pension']

    _training, test = load_from_csv()
    test = expand_content_ids(test, on='final_click_url')

    for query in eyeball_queries:
        print(query)
        print('-----')
        counts = test[test.search_term_lowercase==query].title.value_counts()
        print(counts.head())
        print('')