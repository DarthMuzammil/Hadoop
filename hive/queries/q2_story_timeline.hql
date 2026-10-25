-- Q2. Hour-by-hour views of the 6 biggest English stories (time series behind the spikes).
-- Joins the small spike table with the large hourly table (Hive converts this to a map-side join).
WITH top_en AS (
  SELECT title, MAX(excess_views) AS m
  FROM spikes
  WHERE lang = 'en'
  GROUP BY title
  ORDER BY m DESC
  LIMIT 6
)
SELECT p.hour, pretty_title(p.title) AS article, p.views
FROM pageviews_hourly p
JOIN top_en t ON p.title = t.title
WHERE p.lang = 'en'
ORDER BY article, p.hour;
