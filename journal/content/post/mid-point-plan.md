---
title: "Half way through - what's left to do"
date: 2018-04-22T9:00:01Z
tags: ["Week 5"]
---

I have 6 or 7 weeks left. Which is basically 6 or 7 days + however much of my own time I can spend on it. There's a lot left to do.

I think there are broadly 5 things for me to focus on, but I don't think I'll be able to achieve everything.

## 1. Get more data in
- Add in data from the last week
- Tokenize and stem queries so similar ones can be grouped together
- Investigate whether it makes sense to group queries with the same result sets

## 2. Get better results
- Account for error in the calculated relevance in a way that makes sense, or filter out documents I'm not confident about
- Make sure my testing code works properly and the metrics make sense
- Compare my implementation to [PyClick's implementation](https://github.com/markovi/PyClick/blob/master/pyclick/click_models/SDBN.py)
- Change my training/test split to ensure the split is the same for each query
- Try out the DBN model

## 3. Devote more time to learning
- Read up more on open source libraries and similar projects
- Get better at writing idiomatic pandas code.
- Find a good stats book
- Audit the rest of the coursera Probabilistic Graphical Model's course

## 4. Apply the results from the click model
- Build a tool to suggest best bets for a query (for content designers)
- Build a tool to compare two rankings (for search teams)
- Show the thing

## 5. Try learning to rank (if there's time?)
- Engineer features
- Train a LTR model
- Build a prototype LTR system with the Elasticsearch LTR plugin
- Give a presentation on what I found