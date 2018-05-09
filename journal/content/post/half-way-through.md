---
title: "Half way through - what I've done so far"
date: 2018-04-22T9:00:00Z
tags: ["Week 5"]
---

We are half way through the accelerator program and Thursday morning I had a half day meeting and retrospective with the other accelerants. It was really good to have a chance to talk to everyone, but I'm finding the limited time very stressful.

I'm not sure yet whether the program is going to be 11 or 12 weeks, because we started a week late but there is a venue booking for presentations at the end which hasn't been changed yet.

## Where I've got to so far

- I've implemented code to extract the data I need, filter and transform it, and also load it into a PostgreSQL database
- I've implemented the Simplified Dynamic Bayesian Network (SDBN) click model
- I can generate a new ranking for each query using the model
- I've tested it with a small dataset covering the top 100 queries (but my model makes things slightly worse at the moment)

## Challenges

### Data I thought existed doesn't actually exist
I started the project thinking that a year's worth of data had been exported to BigQuery, but it wasn't. So I only have the data collected since a couple of weeks ago. This means I will have less data on the "long tail" of search queries, and anything that is seasonal.

### Managing data is hard
I've written a lot of my code quite experimentally and accumulated a few different steps that extract, transform or load data. Initially I was a bit lax about naming files and I started to lose track of where each dataset came from. But I've made to sure to always include the date range used when extracting the data in all my filenames.

Later on I decided to organise everything so I have a directory structure like this:

```
data/
     week1/
           thing_i_did/
                       raw/
                       cleaned/
                       README
```

This is great for storing intermediate datasets because I can go back to stuff I did earlier and still understand it.

However I also want to be able to incrementally fetch and process new data, so now I'm storing all the final data in a database, and I query that for training my click models instead of updating a huge CSV.

### Accounting for error
What I've noticed when investigating the results so far is that my code tends to have very unrealistic perceptions of the lowest ranked results. There's a document
that was clicked only 8 times and skipped twice, and at the moment my model assigns that
an 80% attractiveness. This makes no sense, because I'm generalising from just a few people, who represent less than 1% of the sessions for that query.

I thought about just filtering these out, but my mentor suggested assigning an error so that every relevance judgement has an upper and lower bound. Then I could rank based on
the lower bounds.

I think you can view the clicked/skipped/final click counts for a document/query pair as coming from a Poisson probability distribution. The expected mean would be the number of searches times some underlying probability, and the standard deviation is the square root of the mean. But I don't know if I can do anything with this. I'm only sampling each distribution once, so I don't actually calculate the mean or standard deviation directly.

The other thing I tried was looking at the average and standard deviations of all the counts for individual queries, and using that as a measure of error. I think this is problematic because quantities like number of clicks are typically heavily weighted towards one result - you might have 80% of the clicks in the top couple of results and 20% in the rest, which gives you a huge standard deviation. I tried this on Friday and got terrible results back, so I want to rethink this.