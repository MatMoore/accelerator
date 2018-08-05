---
title: "Building a tool to benchmark search: Results and lessons learnt"
date: 2018-08-05T13:00:00+01:00
tags: ["Week -1"]
---

This is the second in a series of blog posts about what I worked on for my data science accelerator project at [GDS](https://www.gov.uk/government/organisations/government-digital-service). It follows [part 1: motivation](/post/project-writeup-motivation).

## What I built
During the 11? 12? days of the programme, I built a [data pipeline](https://github.com/MatMoore/accelerator) that fitted a simplified dynamic bayesian network model to my data about search clicks.

As I alluded to in the previous post, this model allows me to estimate the probability of a
document being relevant to users who entered a certain search term.

I then built a tool that used this model to compare search results to an "ideal" ranking where everything is ordered according to the model's probabilities. I made this part of [search performance explorer](https://github.com/alphagov/search-performance-explorer/pull/62), which is an app we previously built for evaluating changes to search.

## This is an MVP
I intentionally kept the tool as simple as possible (just [59 lines of ruby code](https://github.com/alphagov/search-performance-explorer/blob/master/lib/health_check/click_model_benchmark.rb)), because I didn't have much time, and this was an experiment. There was no point in adding a bunch of features before I validated whether the tool is useful.

I would have liked to try using the tool to change the search implementation as part of the project, but unfortunately I ran out of time to do this.

The essential requirement for me was to make the output **unambiguous** and **easy to interpret**. The tool we used to use to evaluate search just ran a number of checks, and counted how many passed, so it was very difficult to make decisions based on its output.

For this tool, I made it output a score as a percentage. It looks something like this:

```bash
probate: 0.72
tax credits: 0.58
passports: 0.7
mot: 0.66
apprenticeships: 0.84
childcare: 0.49
p45: 0.82
dart charge: 0.69
tax rebate: 0.6
companies house: 0.72
[....]

TOTAL SCORE: 67.6%
```

If you can get it to significantly increase the overall score, then you are on to something.

I considered weighting the performance of the various search terms according to usage, but in the end I just kept everything the same, because the search terms I was using weren't representive of user behaviour as a whole.

## I only looked at high volume queries
At the beginning of the project I discovered that the data I wanted wasn't being properly exported to BigQuery, so instead of having a years worth of data, I only worked with about a month's worth. This limited what I could do, and I ended up only looking at the highest volume search terms.

## The tool might not work
Early on I talked with my mentor about evaluation metrics, and we decided to evaluate the model by measuring the number of sessions where the users "chosen" document would be ranked higher by the model than under the current implementation of search. But that metric is very conservative as the test users' chosen documents are strongly influenced by position bias.

Since I didn't come up with a better metric, I wasn't able to confidently say that using my tool will lead to better search results. Ultimately I won’t know how useful it is until it’s been used in the real world.

I watched a recording of a [lecture by Olivier Chapelle](https://www.youtube.com/watch?v=gvGfpc7dtMg) where he talks about the difficulty of evaluating click models and why he doesn't just use the [likelihood](https://en.wikipedia.org/wiki/Likelihood_function) when comparing to other models. His method looked specifically at the model's ability to predict clicks when a result is in position 1, which is equivalent to the model's attractiveness parameter. I think this makes sense but it wasn't something I could replicate with my data because GOV.UK search results are very stable and the top result doesn't change often.

## The code quality could be better
I wrote some horrific code for this project, and it caused me a lot of problems.

I started out with the assumption that pandas was the right tool to use, but user session data didn't really fit a tabular format, so I would have been better off just writing plain python and only using pandas for data exploration.

I ended up storing the cleaned data I was working with in a relational database because it was much easier for me to manipulate that way.

In some cases I got confused by may own names for things. I would use one definition when extracting the data, and then another when using it, because it was hard to remember stuff week to week.

It took me a surprisingly long time to realise that I could save intermediate data between processing steps rather than running everything from scratch every time, but that helped a lot.

I also regret not including human readable identifiers into every dataset I worked with. My data was full of UUIDs like "443cf66f-9a51-4bac-9998-b0720cceba7c" and whenever I was debugging something I had to work around it by joining in another dataframe.

## Further reading

This is going to be the last post on this blog, but if you want to read more about this kind of thing, check out the resources below:

- [Click models for web search](https://pdfs.semanticscholar.org/0b19/b37da5e438e6355418c726469f6a00473dc3.pdf) -  a review of different click models
- [PyClick](https://github.com/markovi/PyClick) - a python library of click models
- [A dynamic bayesian network model for web search ranking](https://youtu.be/gvGfpc7dtMg) - a lecture at microsoft research
- [So your data science project isn't working](https://medium.com/@skyetetra/so-your-data-science-project-isnt-working-7bf57e3f12f1) - how to not get discouraged
- [Normalised discounted cumulative gain](https://en.wikipedia.org/wiki/Discounted_cumulative_gain#Normalized_DCG) - the metric I used to calculate the overall score
- [Clickstream mining for learning to rank training data](https://trac.xapian.org/wiki/GSoC2017/LetorClickstream/ProjectPlan) - a google summer of code project that solves the same problem for the Xapian open source search engine