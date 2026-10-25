# WikiTrend — Real-Time Breaking-News Detection from Wikipedia Traffic Using Hadoop

Big Data Analytics (26ECAE417) course project.

When something big happens (an election, a disaster, a celebrity death), millions of people look it
up on Wikipedia within the hour. WikiTrend processes Wikimedia's hourly pageview logs with
**Hadoop MapReduce**, learns each article's normal traffic level, and flags articles whose traffic
suddenly jumps far above normal (**z-score anomaly detection**). The output is a ranked list of
trending/breaking stories per hour, analysed further with **Hive**.

Demo dataset: 30 hours of logs, 7 Sep 2022 18:00 → 8 Sep 2022 23:00 UTC (**5.6 GB in HDFS**),
covering the death of Queen Elizabeth II, announced at 17:30 UTC on 8 Sep.

## Architecture

```
 dumps.wikimedia.org ──► local disk (.gz) ──► HDFS /wikitrend/raw   (30 files, 5.6 GB, uncompressed)
                                                      │
               ┌──────────────────────────────────────┘
               ▼
 Job 1  Aggregate        clean + filter, merge desktop/mobile, sum views     ──► /wikitrend/out/agg/hour=X/
        (Mapper + Combiner + Reducer, MultipleOutputs -> one partition per hour)
               ▼
 Job 2  SpikeDetection   secondary sort (article, hour) -> per-article time series,
                         sliding 6-hour baseline, z-score + ratio test          ──► /wikitrend/out/spikes/hour=X/
               ▼
 Job 3  TopSpikes        in-mapper Top-N, custom hour partitioner, global Top-N ──► /wikitrend/out/top/hour=X/
               ▼
 Hive   external partitioned tables + RCFile table + custom UDFs ──► results/*.tsv ──► charts (matplotlib)
```

**Real-time mode** (micro-batch stream processing): a *producer* drops each new hourly file into
`/wikitrend/landing`; a *consumer* detects it, runs the three jobs on just that hour (using the
previous 6 hours already stored in HDFS as the baseline), and prints the trending list.

## Repository layout

| Path | What |
|---|---|
| `src/main/java/com/wikitrend/` | MapReduce code (Java 8) |
| `src/test/java/` | JUnit tests (parser, hour labels, spike maths) |
| `conf/` | Hadoop + Hive configuration for a single-node cluster |
| `scripts/` | numbered scripts: install → start → download → load → run → real-time demo → Hive |
| `hive/` | HiveQL table definitions, analysis queries, Java UDFs |
| `viz/make_charts.py` | charts from the Hive results |
| `results/` | query outputs (`*.tsv`), charts, logs from our run |
| `report/` | project report (`WikiTrend_Report.pdf`), its generator, and `team.json` (names/USNs for the cover) |
| `DEMO.md` | step-by-step demo script for the presentation |

## Setup on an Ubuntu VM (one time)

Requirements: Ubuntu 20.04/22.04/24.04, **≥ 8 GB RAM** (see note), **≥ 30 GB free disk**, internet.

```bash
git clone <this repo> ~/Hadoop && cd ~/Hadoop
chmod +x scripts/*.sh hive/*.sh

scripts/01_install_hadoop.sh     # Java 8, Maven, Hadoop 3.3.6, config, format NameNode, build jar
source ~/.bashrc
scripts/02_start_hadoop.sh       # start HDFS + YARN + JobHistory (jps should list 5 daemons)
scripts/03_download_data.sh      # 30 hourly dumps, ~1.5 GB download
scripts/04_load_hdfs.sh          # decompress into HDFS -> 5.6 GB
scripts/05_run_batch.sh          # full 3-job pipeline (~25-40 min on a 4-core VM)
scripts/08_install_hive.sh       # Hive 3.1.3 + Derby metastore
scripts/09_hive_analysis.sh      # Hive tables + 6 analysis queries -> results/*.tsv
python3 viz/make_charts.py       # -> results/charts/*.png
scripts/10_build_report.sh       # rebuild report from YOUR run (fill in report/team.json first)
```

After a VM reboot only `scripts/02_start_hadoop.sh` is needed again. Stop with `scripts/stop_hadoop.sh`.

**Low-RAM VM (4–6 GB):** in `conf/yarn-site.xml` set `yarn.nodemanager.resource.memory-mb` and
`yarn.scheduler.maximum-allocation-mb` to `3072`, copy it to `$HADOOP_HOME/etc/hadoop/` and restart.
Jobs will just run with fewer parallel tasks.

Web UIs: NameNode http://localhost:9870 · YARN http://localhost:8088 · JobHistory http://localhost:19888

## Running

```bash
# Full batch run (all 30 hours)
hadoop jar target/wikitrend.jar batch /wikitrend/raw /wikitrend/out

# One hour (what the real-time consumer runs for each new file)
hadoop jar target/wikitrend.jar hour /wikitrend/landing/pageviews-20220908-180000 /wikitrend/live

# Show the ranking of any processed hour
hadoop jar target/wikitrend.jar show /wikitrend/out 2022-09-08T18 15

# Tuning: Hadoop generic options go BEFORE the command
hadoop jar target/wikitrend.jar -D wikitrend.z.threshold=6 -D wikitrend.min.views=5000 batch /wikitrend/raw /wikitrend/out2
```

| Parameter | Default | Meaning |
|---|---|---|
| `wikitrend.window.hours` | 6 | hours of history used as the baseline |
| `wikitrend.min.history.hours` | 3 | minimum history before an hour is scored |
| `wikitrend.min.views` | 1000 | spike must have at least this many views in the hour |
| `wikitrend.z.threshold` | 4.0 | spike must be ≥ this many standard deviations above the baseline |
| `wikitrend.min.ratio` | 3.0 | spike must be ≥ this many times the baseline mean |
| `wikitrend.noise.floor` | 5 | hourly counts below this are treated as 0 (cuts shuffle size) |
| `wikitrend.top.n` | 25 | spikes kept per hour in the ranking |

## Real-time demo

See [DEMO.md](DEMO.md). In short, open two terminals:

```bash
scripts/07_realtime_consumer.sh                    # terminal 2: watches HDFS and processes each new hour
scripts/06_realtime_producer.sh 2022-09-08T12 2 60 # terminal 1: publishes 12:00 and 13:00 UTC
```

## Spike detection, in short

For each article and each hour *h* with *v* views, the baseline is the previous 6 hours:

```
mean  = average(baseline)          sigma = max(stddev(baseline), sqrt(mean + 1))
z     = (v - mean) / sigma         ratio = v / (mean + 1)         excess = v - mean
spike  ⇔  v ≥ 1000  and  z ≥ 4  and  ratio ≥ 3          ranking: by excess (extra readers)
```

The `sqrt(mean + 1)` floor (Poisson noise) stops articles with a flat baseline of zero from getting an
infinite z-score.
