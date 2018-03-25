---
title: "How does GOV.UK search work at the moment?"
date: 2018-03-17T13:26:14Z
draft: true
tags: ["Week 0"]
---
The [search functionality](https://github.com/alphagov/rummager) on GOV.UK is built using an open source search engine, [Elasticsearch](https://en.wikipedia.org/wiki/Elasticsearch).

In this post I'll explain how GOV.UK search uses elasticsearch to generate search results, and some of the problems with it.

## Indexing

Whenever a new document is published, it automatically gets added to a search index. When you index a document, elasticsearch [analyses the document's text](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis.html), which involves lowercasing, stripping out diacretics, breaking it into tokens, stemming words, substituting synonyms etc. 

We do this for the main text of the page, `indexable_content` plus other document fields like the `title` and `description`.

## Querying
When you type in a search term, we run an elasticsearch query to retrieve
matching documents and rank them in a particular order.

Elasticsearch uses the [TF-IDF algorithm](https://www.elastic.co/guide/en/elasticsearch/guide/current/scoring-theory.html) to match the tokens in the user's search term with the tokens stored in the search index, and retrieve a set of documents. It gives each one a *score*. The higher the score, the higher up a document will appear in the results.

Because we store multiple fields for each document, our elasticsearch query actually involves multiple *subqueries*, and we define *boosts* to "shape" the score given by TF-IDF.

The code that generates this query looks something like this:

```ruby
popularity_boost.wrap(
 format_boost.wrap(
   {
     bool: {
       should: [
         core_query.match_phrase("title"),
         core_query.match_phrase("acronym"),
         core_query.match_phrase("description"),
         core_query.match_phrase("indexable_content"),
         core_query.match_all_terms(%w(title acronym description indexable_content)),
         core_query.match_any_terms(%w(title acronym description indexable_content)),
         core_query.minimum_should_match("all_searchable_text")
       ],
     }
   }
 )
)
```

Essentially there are 9 features, which are combined to produce the ultimate score
of a document.

`format_boost` is an example of one we changed recently. The "format" of a document is decided at publish time and [there are 67 of them](https://www.gov.uk/api/search.json?facet_format=10000&count=0). We use the format to promote certain kinds of content.

A subset of the formats are considered "news-y", and for these the boost depends on how recently the document was published ([view score as a function of document age on Wolfram Alpha](https://www.wolframalpha.com/share/clip?f=d41d8cd98f00b204e9800998ecf8427e5qr62u0si))

### Limitations of this code
We should be able to make this code work a lot better than it actually does. It bakes in a lot of shaky assumptions about what makes documents relevant to people, and the results are sensitive to small changes in the phrasing of the query.

Unfortunately, it's also really hard to change this (or start over) without making it worse. The feedback cycle for new changes is really slow, because we typically have to deploy to production before we can really measure whether we're making things better or worse.

We capture a lot of information about user behaviour through Google Analytics. We know what results users tend to click on, and we can use that to guess at what results should be ranked higher or lower than they actually are. But we don't yet have the infrastructure to use this data to drive product improvement.

### Machine learning for search
Meanwhile, the open source software available for building search systems is getting better and better. There is now a [Learning to rank plugin](https://elasticsearch-learning-to-rank.readthedocs.io/en/latest/) for Elasticsearch that lets you use machine learning to optimise the ranking of search results as a secondary step after fetching the most likely matches.

This is really promising, but it's even more reliant on [data and data infrastructure](https://opensourceconnections.com/blog/2017/07/05/infrastructure_for_ltr/).