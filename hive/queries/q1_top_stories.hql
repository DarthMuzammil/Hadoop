-- Q1. The biggest stories of the day: every article that spiked, ranked by its largest hourly excess
SELECT lang,
       pretty_title(title)        AS article,
       MIN(hour)                  AS first_detected,
       COUNT(*)                   AS hours_trending,
       MAX(views)                 AS peak_views,
       MAX(excess_views)          AS max_excess_views,
       ROUND(MAX(z_score), 1)     AS max_z,
       wiki_url(lang, title)      AS url
FROM spikes
GROUP BY lang, title
ORDER BY max_excess_views DESC
LIMIT 25;
