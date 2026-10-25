# Demo script (about 10 minutes)

Do this **before the demo** (the batch run takes a while):

```bash
scripts/02_start_hadoop.sh          # if the VM was rebooted
scripts/05_run_batch.sh             # only if /wikitrend/out does not exist yet
scripts/09_hive_analysis.sh         # only if results/ is empty
```

Have these open: a terminal, http://localhost:9870 (HDFS) and http://localhost:8088 (YARN).

---

### 1. The problem (1 min)
"Wikipedia gets ~20 million article views per hour. When news breaks, readers rush to the related
articles within minutes. Detecting those rushes in near real time tells us *what the world is
talking about right now*, without reading a single news article."

### 2. The data is in HDFS (1 min)

```bash
hdfs dfs -ls -h /wikitrend/raw
hdfs dfs -du -s -h /wikitrend/raw                      # 5.2 G (5.6 GB)
hdfs fsck /wikitrend/raw | grep -E "Total size|blocks|Status"
hdfs dfs -cat /wikitrend/raw/pageviews-20220908-180000 | head -5
```
Point out: 30 hourly files, 60 blocks, HEALTHY. Raw line = `language page views 0`.
In the NameNode UI: *Utilities → Browse the file system → /wikitrend/raw*.

### 3. Real-time detection, live (6 min)

Story: on 8 Sep 2022 at ~12:30 UTC Buckingham Palace said the Queen's doctors were "concerned for
her health". The death was announced at 17:30 UTC. We replay the day as if it were live.

Terminal 2 (consumer, start first):
```bash
scripts/07_realtime_consumer.sh
```
Terminal 1 (producer):
```bash
scripts/06_realtime_producer.sh 2022-09-08T12 2 60
```
Each hour takes about 3 minutes to process (3 YARN jobs). Narrate while it runs:
- Show the YARN UI (http://localhost:8088): Aggregate → SpikeDetection → TopSpikes applications.
- **12h result**: *Elizabeth II* (z ≈ 293), *Operation London Bridge* (the UK's plan for the Queen's
  death, z ≈ 827) and *List of longest-reigning monarchs* are flagged. **The system detected the
  story 5.5 hours before the official announcement**, only from reader behaviour.
- **13h result**: *Balmoral Castle* (where she was), *Charles, Prince of Wales*, the Spanish article.

Then jump ahead with the stored results (instant):
```bash
hadoop jar target/wikitrend.jar show /wikitrend/out 2022-09-08T18 15   # announcement: 8 languages at once
hadoop jar target/wikitrend.jar show /wikitrend/out 2022-09-08T20 10   # Charles III, Operation Unicorn
hadoop jar target/wikitrend.jar show /wikitrend/out 2022-09-08T23 10   # Japan wakes up to the news
```
Point out *Charles, King of the United Kingdom* at 18h with baseline 0: a page that did not exist
an hour earlier (renamed/created by editors as the news broke).

### 4. How it works (2 min) — open the code
- `AggregationJob`: mapper parses + cleans, **combiner** sums desktop+mobile, reducer writes
  **hour partitions** with MultipleOutputs.
- `SpikeDetectionJob` + `ArticleHourKey`: **secondary sort**, so the reducer sees each article's hours
  in time order; sliding 6-hour baseline; z-score test (`SpikeDetector`).
- `TopSpikesJob`: **in-mapper Top-N** + custom **HourPartitioner**.
- Data-quality counters printed after each job (malformed lines, non-article pages, …).

### 5. Hive analysis + charts (1 min)

```bash
cd ~/hive_metastore && hive
USE wikitrend;
ADD JAR ~/Hadoop/hive/wikitrend-udf.jar;
CREATE TEMPORARY FUNCTION pretty_title AS 'com.wikitrend.hive.PrettyTitleUDF';
SELECT hour, rnk, lang, pretty_title(title), views, z_score FROM top_trending
WHERE hour='2022-09-08T18' AND rnk <= 10;
```
Then show `results/charts/` (story timeline, news intensity per hour, top stories).

### Likely questions
- *Why is it "real-time" if MapReduce is batch?* — Micro-batching: Wikimedia publishes one dump per
  hour, and each one is processed as soon as it lands, re-using state (previous hours' aggregates)
  kept in HDFS. The same design as Spark Streaming's micro-batches, built on plain MapReduce.
- *Why z-score and not just "views > X"?* — Popular pages are always big; the question is "unusual for
  this page". The z-score is relative to each article's own history.
- *Why the `sqrt(mean+1)` floor?* — An article with 0,0,0 views has standard deviation 0, which
  would make every visit infinitely surprising. Poisson noise gives a natural minimum.
- *Why store the data uncompressed in HDFS?* — gzip is not splittable; uncompressed files split into
  128 MB blocks, so each hour gets 2 parallel map tasks.
