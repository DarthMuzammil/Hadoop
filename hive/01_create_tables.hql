-- WikiTrend: Hive layer over the MapReduce output in HDFS.
-- Run with:  hive --hivevar OUT=/wikitrend/out -f hive/01_create_tables.hql
-- The MapReduce jobs already write Hive-style partition folders (hour=YYYY-MM-DDTHH), so the
-- tables are EXTERNAL: Hive only adds a schema on top, and dropping a table never deletes data.

CREATE DATABASE IF NOT EXISTS wikitrend;
USE wikitrend;

-- Job 1 output: views per article per hour (desktop + mobile merged)
CREATE EXTERNAL TABLE IF NOT EXISTS pageviews_hourly (
  lang   STRING,
  title  STRING,
  views  BIGINT
)
PARTITIONED BY (hour STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION '${hivevar:OUT}/agg';

-- Job 2 output: every detected spike
CREATE EXTERNAL TABLE IF NOT EXISTS spikes (
  lang           STRING,
  title          STRING,
  views          BIGINT,
  baseline_mean  DOUBLE,
  sigma          DOUBLE,
  z_score        DOUBLE,
  ratio          DOUBLE,
  excess_views   BIGINT
)
PARTITIONED BY (hour STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION '${hivevar:OUT}/spikes';

-- Job 3 output: top-N trending articles per hour
CREATE EXTERNAL TABLE IF NOT EXISTS top_trending (
  rnk            INT,
  lang           STRING,
  title          STRING,
  views          BIGINT,
  baseline_mean  DOUBLE,
  z_score        DOUBLE,
  ratio          DOUBLE,
  excess_views   BIGINT
)
PARTITIONED BY (hour STRING)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION '${hivevar:OUT}/top';

-- Register the hour=... folders written by MapReduce as partitions
MSCK REPAIR TABLE pageviews_hourly;
MSCK REPAIR TABLE spikes;
MSCK REPAIR TABLE top_trending;

SHOW PARTITIONS top_trending;

-- Columnar copy of the spike table in RCFile format (row groups stored column-wise):
-- analytical queries read only the columns they need.
DROP TABLE IF EXISTS spikes_rc;
CREATE TABLE spikes_rc (
  hour           STRING,
  lang           STRING,
  title          STRING,
  views          BIGINT,
  baseline_mean  DOUBLE,
  z_score        DOUBLE,
  ratio          DOUBLE,
  excess_views   BIGINT
)
STORED AS RCFILE;

INSERT OVERWRITE TABLE spikes_rc
SELECT hour, lang, title, views, baseline_mean, z_score, ratio, excess_views FROM spikes;

SELECT COUNT(*) AS spike_rows FROM spikes_rc;
