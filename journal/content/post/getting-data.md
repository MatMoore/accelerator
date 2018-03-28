---
title: "Getting some data"
date: 2018-03-28T19:00:00Z
tags: ["Week 1"]
---
This week my main goal was to get some data and explore it.

I spent most of it figuring out how the Google Analytics API works. I found this quite daunting at first because the "getting started" documentation doesn't link to a proper reference, and I didn't have a good understanding of the concepts behind google analytics. But I found a couple of useful resources:

1. [The dimensions and metrics explorer](https://developers.google.com/analytics/devguides/reporting/core/dimsmets) gave me most of the information I needed to query the API. I used it in conjunction with internal documentation on how we've set up custom dimensions/custom variables.

2. [The API reference for batchGet](https://developers.google.com/analytics/devguides/reporting/core/v4/rest/v4/reports/batchGet) documents the structure of the API request. Initially I was confused because if you go to the documentation for the python client library, and follow the obvious links to reference documentation, you end up [here](https://developers.google.com/resources/api-libraries/documentation/analyticsreporting/v4/python/latest/index.html). Which is completely useless. Thankfully if you know the JSON API representation you can guess what you need to pass to the python client library.

## Variables I'm using
We use the "E-commerce" functionality of GA to track how users interact with site search.

So a piece of content is modelled as a "product" and a search result page is modelled as a "product list".

The code that implements this is here: [https://github.com/alphagov/static/blob/master/app/assets/javascripts/analytics/ecommerce.js](https://github.com/alphagov/static/blob/master/app/assets/javascripts/analytics/ecommerce.js)

This gives us the following set of dimensions and metrics:

|name|type|meaning|
|----|----|-------|
|ga:productSku | Dimension | Internal ID or path for a content item |
|ga:productListName | Dimension | "Site search results" |
|ga:productListPosition | Dimension | The position a link was shown in |
|ga:dimension71 | Dimension | The user's search term |
| ga:dimension95 | Dimension | The [client ID](https://developers.google.com/analytics/devguides/collection/analyticsjs/cookies-user-id) |
|ga:productListClicks | Metric | The number of times a link was clicked |
|ga:productListViews | Metric | The number of times a link was viewed |

I was able to [write a query](https://github.com/MatMoore/accelerator/blob/master/ga.py#L104) that used all of these dimensions together, so that there are N rows in my report for every "search session", where each search session is a different combination of user + search term, and N is the number of the search results they saw (I filtered this to just look at the first page).

## Exploring the data
I extracted a very small amount of data and loaded it into a jupyter notebook so I could explore the different fields.

I used some of the [summarisation methods in pandas](https://github.com/pandas-dev/pandas/blob/master/doc/cheatsheet/Pandas_Cheat_Sheet.pdf) and plotted some histograms to look at the values.

Some of the things I noticed:

- We're truncating the search term to 100 characters. A small but not insignificant amount of queries are truncated (I don't think this is a problem because 100 characters is enough to distinguish the user's intent)
- productListClicks is very binary (users either click something or don't click it) but productListViews shows that the same results are often viewed multiple times, suggesting people are bouncing back to the result page
- My code for paginating through the report had a bug on it so I accidently dropped the last page. Whoops. 

## Next steps

I also had a look at Google BigQuery, which contains an export of the raw analytics data.
I want to try and use this next so that I can more easily fetch a larger dataset, while being able to look at things that happened within a session.

The schema is documented here: [https://support.google.com/analytics/answer/3437719?hl=en](https://support.google.com/analytics/answer/3437719?hl=en).

My assumption is that this will let me look at what happened after a user clicked on a search result. We don't have a very clear way to tell if a user was satisfied after clicking a link, but we should be able to make a guess based on the time spent on the page and whether they went back to the results page afterwards.