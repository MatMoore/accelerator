---
title: "Predicting search result relevance with a click model"
date: 2018-04-08T10:00:00Z
tags: ["Week 3"]
markup: mmark
---

For my project I want to use search logs to model user behaviour on GOV.UK search.

The approach I want to follow is based on a paper titled
[A Dynamic Bayesian Network Click Model for Web Search Ranking](http://olivier.chapelle.cc/pub/DBN_www2009.pdf) (Chapelle and Zhang 2009)

## Overview of the paper
The Dynamic Bayesian Network model is one of many [click models](https://clickmodels.weebly.com/about.html) for modelling search behaviour in terms of random variables. Given a search engine result page, a click model should be able to predict the probability that a user will click on any of the links on the page.

The paper starts by introducing the Dynamic Bayesian Network (DBN) model in the context of earlier click models. It then discusses some experiments based on web search data:

- Section 5 describes how to parameterise the model in the simplest case (for the full thing they use Expectation Maximization (EM), described in the appendix)
- Section 4.1 predicts the click through rate of position 1 links, to test that the model describes the data
- Section 4.2 predicts relevance of observed (query, url) pairs and compares it to editorial judgements to show that the model is almost as good as getting humans to judge relevance
- Section 4.3 uses the predicted relevance to train a learning to rank (LTR) model, so that they can rank results based on a feature set instead of needing a complete set of relevance estimations for every (url, query) pair at runtime

## What is a DBN?
A dynamic bayesian network is a type of Probabalistic Graphical Model (PGM). This is basically a graph that shows how random variables depend on each other. Random variables can be things you observe, or things that are hidden (latent variables). In this particular case most of the variables in the model are hidden variables.

I've found the [Probabalistic Graphic Models](https://www.coursera.org/learn/probabilistic-graphical-models) course on Coursera useful for understanding this stuff (but I haven't completed it yet).

The "dynamic" part basically means that you are modelling some kind of sequence. In this case a user is examining a list of search results, and the probabality of clicking on any particular link is dependent on the probability of clicking the previous one.

The authors note that this is similar to a Hidden Markov model (HMM). [HMM is a special case of DBN](https://datascience.stackexchange.com/questions/10000/what-is-the-difference-between-a-dynamic-bayes-network-and-a-hmm).

### What the DBN looks like
The model presented in the paper looks like this:
![diagram of the DBN click model](/images/dbn.png)

This says that the probability of a search result being clicked depends on two things: whether the result is "attractive", $$A$$, and whether the user actually bothered looking at that result, $$E$$. Whether the user looks at the next result depends on whether they were satisfied with the result they just clicked on, $$S$$.

The box around the variables means that everything inside the box applies to the whole sequence. So for the first 3 search results, the graph expands to this: 

![expanded diagram of the DBN click model](/images/dbn-expanded.png)

Note that the first result is a special case, because $$E_1$$ doesn't depend on anything else. The user always examines the first result. The probability they click on it just depends on how attractive it is.

### Assumptions of the model
These are the basic assumptions of them model, which allow us to define conditional probability distributions for each of the variables.

1. Links are clicked if and only if the user examines them and the URL is attractive.
2. Attractiveness is an inherent quality of the URL, parameterized by the $$a_u$$ variable
3. After a clicking a link the user may or may not be satisfied. This is also an inherent quality of the URL, parameterised by $$s_u$$
4. Users stop examining new results once satisfied with a result they clicked on
5. There is a probability $$1-\gamma$$ of abandoning a search after clicking a result and not being satisfied. The simplified model ignores this.
6. Users examine all links in order and don’t skip over a link without examining it.
  - In section 4 they say 3% of sessions contain out of order clicks, which goes against this assumption. They discarded the data but said they could also just ignore the ordering here (i.e. treat the sessions as if the user clicked the links in the ranked order). I think this is what I'm going to do initially, because it makes it easier to get the data I need.

## Extracting relevance from the trained model
The DBN model has 3 sets of parameters:

- A single variable $$\gamma$$, which is a measure of how determined users are to find what they're looking for. In the simplified model I'm going to start with, $$\gamma = 1$$, meaning users are assumed to examine everything on the page until they find a relevant result.
- $$a_u$$, defined for every (query, result) pair. This is the probability the result looks relevant for that query.
- $$s_u$$, defined for every (query, result) pair. This is the probability the result actually satisfies the user.

They define relevance as the product of $$a_u$$ and $$s_u$$, so once you've trained the model you know what's relevant and what isn't, and you can generate an optimal ranking that puts the most relevant stuff on the top.

This can then be used as training data to learn a ranking function that can handle any query (section 4.3). The authors found this worked almost as well as using editorial relevance judgements.

## Training the simplified model
For the simplified model where $$\gamma=1$$, the algorithm for optimising the parameters is basically just counting things.

``` python
a = {}
s = {}
for u in urls:
  a[u] = Count(numerator=0, denominator=0)
  s[u] = Count(numerator=0, denominator=0)

for session in sessions:
  # Everything above and including the last clicked URL
  for u in session.examined_urls:
    a[u].denominator += 1

  for u in session.clicked_urls:
    a[u].numerator += 1
    s[u].denominator += 1

  s[session.final_clicked_url].numerator += 1
```

The calculation of $$a_u$$ is similar to the overall clickthrough rate, but it takes into account what the user is likely to have seen, rather than counting everything displayed on the page.

$$s_u$$ is just the percentage of clicks where the user doesn't try another result afterwards.

The authors took some steps to filter the data before splitting it into training and test sets:
- Ignore anything that's not on the first page of search results (in their case this is 10 links, for GOV.UK it’s 20 links)
- Discard all queries with < 10 sessions
- Discard sessions with out of order clicks (see above)

### Beta priors
In the paper they include a [beta prior](https://en.wikipedia.org/wiki/Beta_distribution) for both a and s. So the actual values of $$a_u$$ and $$s_u$$ are:

```python
a_u = (a[u].numerator + alpha_a) / (a[u].denominator + alpha_a + beta_a)
s_u = (s[u].numerator + alpha_s) / (s[u].denominator + alpha_s + beta_s)
```

I don’t really understand this at the moment, but presumably I'm supposed to have some prior knowledge about $$a_u$$ and $$s_u$$.

In theory I do have some additional data about GOV.UK pages I could use, but it's independent of what the user was looking for, so I don't know if it's applicable here.