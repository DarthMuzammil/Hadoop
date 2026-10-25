-- Q3. "News intensity" per hour: how many articles spiked and how many extra readers they drew
SELECT hour,
       COUNT(*)                   AS spikes,
       COUNT(DISTINCT lang)       AS languages,
       SUM(excess_views)          AS total_excess_views
FROM spikes
GROUP BY hour
ORDER BY hour;
