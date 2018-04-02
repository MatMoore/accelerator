---
title: "Data problems"
date: 2018-04-02T14:00:00Z
tags: ["Week 2"]
---
This week was really unproductive. I hit some roadblocks with the data so I didn't accomplish what I set out to do on Thursday. I'm finding this really stressful at the moment as I'm really worried that I won't be able to get the data I need to actually do the project I proposed. 😞

## What I planned to do Thursday

My aim for this weak was to work out how to use Google BigQuery to fetch the data I need instead of the google Analytics API, because:

1. It's really slow to extract data from the API (it took me a couple of hours just to get one day's worth of data)
2. The data I get from the API summarises what happens in a search session, but doesn't show me the individual click events and what order they happened in

The 2nd part is important because the last link clicked within a search session can be seen as an endorsement of the link for that query by the user. If I train a learning to rank model, I want the model to be able to predict what the final click was for a test dataset. If I can confidently predict that a user will choose result #4 over result #1-3 for a given query (while accounting for position bias), then it's reasonable to generate a new ranking with #4 at the top.

Using last click as a measure of satisfaction assumes that users are very persistent and will keep looking for the best result rather than leaving the site straight away if they're not satisfied after clicking a link. This probably isn't super realistic, but it's a starting point and I can weaken this assumption later on if it doesn't work well.

The raw data I want to extract from BigQuery should have these columns:

- sessionId (fullVisitorId + visitId)
- search term
- final URL clicked
- ranking of final URL clicked

## The problem

When I query BigQuery, I have access to all the fields defined in the [BigQuery export schema](https://support.google.com/analytics/answer/3437719?hl=en).

This allows me to query individual sessions, and "hits", which are events like individual pageviews.

There are nested fields such as "hits.product.productListName" which appear to capture the same Ecommerce events I'm querying through the API, but whenever I write BigQuery queries that touch these fields, I get no data back - all these fields appear to be null.

I'm going to try and get help from my coworkers with this, because I can't work out why this doesn't work and even very simple queries don't return what I expect. I'm really hoping someone has written a query involving these fields before.

Another problem I ran into is that while I have permissions to run any query I want, I don't think I can actually extract the data. [The way I planned on doing this requires creating a table](https://cloud.google.com/bigquery/docs/exporting-data#export_limitations), which I don't have permission to do at the moment. That said, I could also run the query from python, which I haven't tried yet.

## What I did instead

Although I haven't figured out how to get the data I need out of BigQuery, I learned a bit about how to use BigQuery itself.

It turns out there are two SQL dialects you can use with it. I started out using Legacy SQL, which you have to opt-out of, even though all the documentation steers you away from it. I also had
a bunch of example queries written in this dialect.

Legacy SQL is very bespoke to BigQuery, but I've found it slightly easier to write so far. This is because BigQuery makes heavy use of these "nested fields". With legacy SQL, it will normally "unnest" them for you automagically, so you can treat it as if you've joined in another table, but you don't actually have to write a join clause for it.

Standard SQL is the newer thing, and you have to explcitly deal with these nested fields. However, it's slightly easier to do certain things because it's SQL 2011 compliant, so
I can use write queries the same way I would with Postgres or any other DBMS.

I ended up writing a [huge SQL query](https://github.com/MatMoore/accelerator/blob/master/queries/sequences.sql) that fetches me all hits in a search session. It currently includes all pages the user went to after hitting a search page, but this could easily be refined by using the referer page to filter out anything that was not a direct link from search.

What this doesn't tell you is what position the link was in when the user clicked it. This comes from the Ecommerce data which I can't get to work. I thought it would still be useful to write this as an exercise, so that if I do figure out to query the ecommerce data, I can adapt this to return what I want.

## Backup plan - keep using the API
While I was looking at BigQuery I also extended my code for querying the google analytics API, so that it can fetch data for longer periods of time (in 1 hour chunks).

This sort of gives me the data I need but can't tell me which order things were clicked in. I can't use this to determine the last clicked link, unless I just assume it's always the clicked result with the highest rank.

I think this is an option I could explore if I need to, but it wouldn't be as reliable as using BigQuery and it would take forever to run if I wanted to extract data for several months. So I'm not very confident in this approach.