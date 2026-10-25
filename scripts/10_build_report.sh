#!/usr/bin/env bash
# Rebuilds the charts and the project report from YOUR run (results/*.tsv and results/logs/*.log).
# Needs: 05_run_batch.sh, 09_hive_analysis.sh and (optionally) one real-time demo run done before.
set -euo pipefail
source "$(dirname "$0")/env.sh"
LOGS="$PROJECT_DIR/results/logs"; mkdir -p "$LOGS"

: > "$LOGS/show_hours.log"
for h in 2022-09-08T11 2022-09-08T12 2022-09-08T13 2022-09-08T18; do
  hadoop jar "$JAR" show "$HDFS_OUT" "$h" 15 2>/dev/null >> "$LOGS/show_hours.log"
done

python3 "$PROJECT_DIR/viz/make_charts.py"
python3 "$PROJECT_DIR/report/build_report.py"
if node -e "require('playwright')" 2>/dev/null; then
  node "$PROJECT_DIR/report/html_to_pdf.js"
else
  echo ">> Open report/WikiTrend_Report.html in Chrome/Firefox and use Print -> Save as PDF (A4)."
fi
