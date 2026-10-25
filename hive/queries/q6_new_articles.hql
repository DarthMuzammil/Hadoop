-- Q6. Articles "born" during the event: pages with (almost) no traffic in the previous hours that
-- suddenly draw thousands of readers - typically new or renamed articles created by editors as the
-- news broke. Runs on the columnar RCFile copy, which reads only the columns used here.
SELECT hour, lang, pretty_title(title) AS article, views, ROUND(baseline_mean, 1) AS baseline
FROM spikes_rc
WHERE baseline_mean < 10 AND views >= 10000
ORDER BY views DESC
LIMIT 15;
