#!/usr/bin/env bash
# Download DATA_HOURS consecutive hourly Wikipedia pageview dumps starting at DATA_START (UTC).
# 30 hours = ~1.6 GB compressed, ~5.5 GB uncompressed.
# Source: https://dumps.wikimedia.org/other/pageviews/  (public, no login needed)
set -euo pipefail
source "$(dirname "$0")/env.sh"

mkdir -p "$LOCAL_DATA"
for i in $(seq 0 $((DATA_HOURS - 1))); do
  ts=$(date -u -d "$DATA_START UTC + $i hour" +%Y%m%d-%H)
  y=${ts:0:4}; m=${ts:4:2}
  f="pageviews-${ts}0000.gz"
  if [ -s "$LOCAL_DATA/$f" ] && gzip -t "$LOCAL_DATA/$f" 2>/dev/null; then
    echo "   $f already downloaded"; continue
  fi
  echo ">> $f"
  curl -sSf --retry 3 -o "$LOCAL_DATA/$f" "https://dumps.wikimedia.org/other/pageviews/$y/$y-$m/$f"
done
ls "$LOCAL_DATA" | wc -l
du -sh "$LOCAL_DATA"
