WITH search_visits as (
    -- All search queries in the context of the session they belong to
    SELECT
        fullVisitorId,
        visitId,
        hits.page.pagePath,
        hits.hitNumber
    FROM
        `govuk-bigquery-analytics.87773428.ga_sessions_*`
    CROSS JOIN UNNEST(hits) as hits
    WHERE
        REGEXP_CONTAINS(hits.page.pagePath, r"/search\?")
        AND hits.type="PAGE"
        AND _TABLE_SUFFIX BETWEEN '20180101' AND '20180101'
    GROUP BY fullVisitorId, visitId, hits.page.pagePath, hits.hitNumber
),

touchpoints as (
    -- All pages visited after the search query page
    -- TODO: these sequences have a defined start point but no defined end point, so
    -- if the user refines their query, all the pages they subsequently visit are still included in the sequence.
    -- We should also identify paths that *end* the sequence so we can trim this down.
    SELECT
      sessions.fullVisitorId,
      sessions.visitId,
      search_visits.hitNumber as searchStartHitNumber,
      search_visits.pagePath as searchPath,
      hits.hitNumber as hitNumber,
      hits.page.pagePath AS touchpoint
    FROM
        `govuk-bigquery-analytics.87773428.ga_sessions_*` as sessions
    CROSS JOIN UNNEST(sessions.hits) as hits
    INNER JOIN search_visits ON (
        sessions.fullVisitorId = search_visits.fullVisitorId
        AND sessions.visitId = search_visits.visitId
        AND hits.hitNumber >= search_visits.hitNumber
    )
    WHERE
      hits.type="PAGE"
      AND _TABLE_SUFFIX BETWEEN '20180101' AND '20180101'
      AND NOT REGEXP_CONTAINS(hits.page.pagePath, r"/search\?")
    GROUP BY sessions.fullVisitorId, sessions.visitId, search_visits.hitNumber, search_visits.pagePath, hits.hitNumber, hits.page.pagePath
)

-- TODO - this does the STRING_AGG multiple times for every search. There is a probably a better way to do this.
SELECT DISTINCT
      fullVisitorId,
      visitId,
      searchStartHitNumber,
      searchPath,
      STRING_AGG(touchpoint, ",") OVER (PARTITION BY fullVisitorId, visitId, searchStartHitNumber, searchPath ORDER BY hitNumber ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS sequence
FROM
    touchpoints