-- Q4. How the news spread across language editions: the #1 trending article of each language
-- in the hour after the announcement (window function ROW_NUMBER per language).
SELECT lang, article, views, baseline, excess_views
FROM (
  SELECT lang,
         pretty_title(title)                 AS article,
         views,
         ROUND(baseline_mean)                AS baseline,
         excess_views,
         ROW_NUMBER() OVER (PARTITION BY lang ORDER BY excess_views DESC) AS rn,
         SUM(excess_views) OVER (PARTITION BY lang)                       AS lang_total
  FROM spikes
  WHERE hour = '2022-09-08T18'
) x
WHERE rn = 1
ORDER BY lang_total DESC
LIMIT 20;
