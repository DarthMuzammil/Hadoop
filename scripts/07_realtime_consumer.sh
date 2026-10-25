#!/usr/bin/env bash
# REAL-TIME DEMO, terminal 2: watches the HDFS landing directory and runs the MapReduce pipeline on
# every new hourly file as soon as it arrives (micro-batch stream processing). Ctrl+C to stop.
#
# For each new hour:  Job 1 aggregate (new hour only)  ->  Job 2 spike detection against the last
# 6 hours kept in HDFS  ->  Job 3 top-N ranking  ->  trending list printed here.
set -uo pipefail
source "$(dirname "$0")/env.sh"

POLL="${POLL:-5}"
LOG="$PROJECT_DIR/results/logs/realtime_demo.log"   # pipeline output also saved here for the report
mkdir -p "$(dirname "$LOG")"; : > "$LOG"
hdfs dfs -mkdir -p "$HDFS_LANDING" "$HDFS_ARCHIVE"
echo ">> Watching $HDFS_LANDING every ${POLL}s (Ctrl+C to stop)"
while true; do
  # Only complete files (in-flight copies are named *._COPYING_), oldest hour first
  files=$(hdfs dfs -ls -C "$HDFS_LANDING" 2>/dev/null | grep -E '/pageviews-[0-9]{8}-[0-9]{6}$' | sort)
  for f in $files; do
    echo
    echo "[$(date +%T)] >> Detected new file: $f" | tee -a "$LOG"
    hadoop jar "$JAR" "$@" hour "$f" "$HDFS_LIVE" | tee -a "$LOG"
    if [ "${PIPESTATUS[0]}" -eq 0 ]; then
      hdfs dfs -mv "$f" "$HDFS_ARCHIVE/"
    else
      echo "!! Processing failed for $f; it stays in landing and will be retried"
      sleep 30
    fi
  done
  sleep "$POLL"
done
