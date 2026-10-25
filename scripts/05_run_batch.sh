#!/usr/bin/env bash
# Full-day batch run of the 3-job MapReduce pipeline over the whole dataset.
set -euo pipefail
source "$(dirname "$0")/env.sh"

hdfs dfs -rm -r -f -skipTrash "$HDFS_OUT" >/dev/null
LOGS="$PROJECT_DIR/results/logs"; mkdir -p "$LOGS"
# extra args are Hadoop generic options, e.g. -D wikitrend.z.threshold=5
# Pipeline output (timings, counters, rankings) is also saved for the report; Hadoop INFO lines go to the console only
time hadoop jar "$JAR" "$@" batch "$HDFS_RAW" "$HDFS_OUT" | tee "$LOGS/batch_run.log"
echo; hdfs dfs -du -h "$HDFS_OUT"
