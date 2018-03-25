---
title: "About this project"
date: 2018-03-17T13:26:13Z
tags: ["Week 0"]
---
Hi! Over the next 3 months I'm going to be spending 1 day a week working on
a project as part of the government [data science accelerator programme](https://www.gov.uk/government/publications/data-science-accelerator-programme/introduction-to-the-data-science-accelerator). I'm encouraged to keep a journal and I thought a blog would be a good way to do it.

## Background
I currently work as a software developer on GOV.UK, the website used by
people in the UK to access government services and information online.

There are about 400,000
different pages on the site, and this content is published by many different
departments and agencies.

A lot of the work I've been involved with has been about how to manage and
structure all this content so users can find stuff.

Part of that work has been on the [search functionality](https://www.gov.uk/search?q=yams), which is what my project will focus on.

## Rough plan
For this project I want to use historical search logs to understand how to improve the ordering
of search results so that users see more **relevant** pages quicker (i.e. the documents are helpful to the user that entered the query).

These are my initial thoughts on what I want to do at the start of the project (they may change!)

1. Given data about what users clicked on, judge the intrinsic relevance of each link displayed on a result page for a query. Prior art: [Search performance dashboard](https://github.com/gds-attic/search-performance-dashboard/blob/master/dashboard/performance.py).
2. Build a tool to evaluate how good search result pages are, based on these judgements. This should be something developers can run for an unreleased version of search, with a representative set of queries, so that they can predict performance *before* deploying the code.
3. Explore [Learning to Rank](https://en.wikipedia.org/wiki/Learning_to_rank) using the relevance judgements as training data.

My next post gives some [background on how GOV.UK search works now](/post/background-govuk-search).
