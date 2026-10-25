-- Q5. Total Wikipedia article traffic per hour for the largest language editions
-- (full scan of the hourly table: shows the daily rhythm of each region).
SELECT hour, lang, SUM(views) AS total_views, COUNT(*) AS articles
FROM pageviews_hourly
WHERE lang IN ('en', 'de', 'ja', 'es', 'ru', 'fr', 'it')
GROUP BY hour, lang
ORDER BY hour, lang;
