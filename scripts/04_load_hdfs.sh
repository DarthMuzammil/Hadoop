#!/usr/bin/env bash
# Decompress each hourly dump straight into HDFS (no temp copy on local disk).
# Stored uncompressed so the files are splittable (2 map tasks per hour) and the dataset is > 4 GB.
set -euo pipefail
source "$(dirname "$0")/env.sh"

hdfs dfs -mkdir -p "$HDFS_RAW"
for gz in "$LOCAL_DATA"/pageviews-*.gz; do
  name=$(basename "$gz" .gz)
  if hdfs dfs -test -e "$HDFS_RAW/$name"; then
    echo "   $name already in HDFS, skipping"; continue
  fi
  echo ">> put $name"
  zcat "$gz" | hdfs dfs -put - "$HDFS_RAW/$name"
done

echo; echo ">> Dataset in HDFS:"
hdfs dfs -ls -h "$HDFS_RAW"
hdfs dfs -du -s -h "$HDFS_RAW"
hdfs fsck "$HDFS_RAW" | grep -E "Total size|Total files|Total blocks|Status" | head -4
