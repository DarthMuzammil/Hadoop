#!/usr/bin/env bash
# REAL-TIME DEMO, terminal 1: simulates Wikimedia publishing a new hourly dump.
# Every INTERVAL seconds the next hour's file is dropped into the HDFS landing directory.
#
# usage: 06_realtime_producer.sh [START_HOUR] [COUNT] [INTERVAL_SECONDS]
#   e.g. 06_realtime_producer.sh 2022-09-08T12 2 60     (12:00 and 13:00 UTC: the story breaks)
#        06_realtime_producer.sh 2022-09-08T17 2 60     (17:00 and 18:00 UTC: the death is announced)
#
# Before streaming, the live system's state (aggregated counts of the previous WINDOW hours) is seeded from
# the batch run, as if the system had already been running all day. Run 05_run_batch.sh once beforehand.
set -euo pipefail
source "$(dirname "$0")/env.sh"

START="${1:-2022-09-08T12}"
COUNT="${2:-2}"
INTERVAL="${3:-60}"
WINDOW=6

start_ts="${START/T/ }:00"
label() { date -u -d "$start_ts UTC + $1 hour" +%Y-%m-%dT%H; }
fname() { date -u -d "$start_ts UTC + $1 hour" +pageviews-%Y%m%d-%H0000; }

echo ">> Resetting live directories"
hdfs dfs -rm -r -f -skipTrash "$HDFS_LANDING" "$HDFS_LIVE" "$HDFS_ARCHIVE" >/dev/null
hdfs dfs -mkdir -p "$HDFS_LANDING" "$HDFS_LIVE/agg" "$HDFS_ARCHIVE"

echo ">> Seeding state: previous $WINDOW hours of aggregated counts"
for i in $(seq "$WINDOW" -1 1); do
  l=$(label "-$i")
  if hdfs dfs -test -d "$HDFS_OUT/agg/hour=$l"; then
    hdfs dfs -cp "$HDFS_OUT/agg/hour=$l" "$HDFS_LIVE/agg/"
    echo "   hour=$l"
  else
    echo "   hour=$l not available (run 05_run_batch.sh first for a full baseline)"
  fi
done

for i in $(seq 0 $((COUNT - 1))); do
  f=$(fname "$i")
  echo
  echo "[$(date +%T)] >> New hourly dump published: $f  -> $HDFS_LANDING/"
  # -cp writes to a ._COPYING_ temp name and renames at the end, so the consumer never sees half a file
  hdfs dfs -cp "$HDFS_RAW/$f" "$HDFS_LANDING/$f"
  if [ "$i" -lt $((COUNT - 1)) ]; then
    sleep "$INTERVAL"
  fi
done
echo; echo ">> Producer finished."
