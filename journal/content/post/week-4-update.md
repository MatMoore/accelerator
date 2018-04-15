---
title: "Week 4 update"
date: 2018-04-08T10:00:00Z
tags: ["Week 4"]
---

I postponed my project day on week 4, and I'm going to make up the time next week instead. This week I joined a new team at work, and I also had some data issues to work out, so I thought I'd make better use of my time this way. I can hopefully work on it uninterrupted on Thursday and Friday.

So this week I've just been working on the project when I've had free time, but I've written code to extract the data I need and I've also loaded it into a postgres database so it's easier for me to query. I finally have API access to the BigQuery export, which is what I wanted to use to get the data. In week 3 I tried using the google analytics API instead, but I ran into a lot of problems with daily and hourly quotas that limited how much data I could actually gather.

Unfortunately I'd assumed all the Ecommerce data was there in BigQuery, but it wasn't. It turns out this data is only exported if you enable a setting in GA, which we hadn't switched on until I noticed it. So rather than a year's worth of data, I have just over a week's worth.

## Limitations of this data
With this dataset, only the top 100 or so queries have over 1000 sessions, but it's still quite useful:

- I can still use these queries to benchmark search performance when making changes
- I can also suggest "best bets" (results that should always be forced to the top for high volume queries)

I think it makes it harder to implement learning to rank, which is what I'd really like to try out, although I will accumulate more data as time goes on.

I think I need to do some grouping of queries so that queries are essentially the same (and are treated the same by the search engine) are counted as one query by my code. I think the easiest way to do this would be to apply the same tokenisation steps Elasticsearch uses.

Some of the top queries are quite hard to improve - people search for things like "log in", or "contact", which search has no context for. So the best result we can come up here will just be a popular service or department home page.

We also get a lot of queries that look like postcodes - we sanitise any data that could be personally identifiable before reporting it to google analytics, so it shows up in my dataset as "[postcode]". I found it strange that a significant number of users would actually put postcodes in there, but the regex we're using to detect postcodes is quite permissive: `/[A-PR-UWYZ][A-HJ-Z]?[0-9][0-9A-HJKMNPR-Y]?(?:[\s+]|%20)*[0-9][ABD-HJLNPQ-Z]{2}/gi`. I think it's possible that this also matches some form names.

## What I've implemented so far
I've started to implement estimation of document relevance using the simplified DBN model. I've gotten to the point where I can spit out a new ranking, but I haven't tested the model yet, and I expect my code is quite buggy.

Interestingly my code thinks the most relevant documents for "self assessment" are [Self Assessment forms and helpsheets: main Self Assessment tax return](https://www.gov.uk/government/collections/self-assessment-helpsheets-main-self-assessment-tax-return)  and [Self Assessment: HMRC manuals](https://www.gov.uk/government/collections/self-assessment-hmrc-manuals) which are at the bottom of the results page at the moment. The third most relevant is currently the 5th result. If this isn't a bug, it would suggest the first page of search results is really unhelpful at the moment.