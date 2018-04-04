SELECT
CONCAT(fullVisitorId,'-',STRING(visitId)) AS sessionId,
hits.product.customDimensions.value as searchTerm,
hits.hitNumber as hitNumber, -- This is the hit number of the results page (for impressions) or the page itself (for clicks)
hits.product.productSKU as contentIdOrPath,
hits.product.productListPosition as linkPosition,
hits.product.isImpression as isImpression,
hits.product.isClick as isClick

FROM TABLE_DATE_RANGE([govuk-bigquery-analytics:87773428.ga_sessions_],TIMESTAMP('2018-04-03'),TIMESTAMP('2018-04-03'))

WHERE hits.product.productListName = 'Site search results'
AND hits.product.productListPosition <= 20
AND hits.product.customDimensions.index = 71
LIMIT 100