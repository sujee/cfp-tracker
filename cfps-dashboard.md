---
tags:
  - dashboard
  - cfp
---

# CFP Dashboard

Compact counts for live CFP events. Archived CFPs are excluded.

## Events by country

```dataview
TABLE WITHOUT ID
  country AS "Country",
  length(rows) AS "Events"
FROM "cfps/data"
WHERE type = "cfp"
  AND !dismissed
  AND country
GROUP BY country
SORT length(rows) DESC
```

---


## Events by topic

Events with multiple topics are counted once in each topic.

```dataview
TABLE WITHOUT ID
  topic AS "Topic",
  length(rows) AS "Events"
FROM "cfps/data"
WHERE type = "cfp"
  AND !dismissed
  AND topics
FLATTEN topics AS topic
GROUP BY topic
SORT length(rows) DESC
```

## Events by month

Months are based on the event date in `event_date`.

```dataview
TABLE WITHOUT ID
  month AS "Month",
  length(rows) AS "Events"
FROM "cfps/data"
WHERE type = "cfp"
  AND !dismissed
  AND event_date
GROUP BY dateformat(event_date, "yyyy-MM") AS month
SORT month DESC
```
