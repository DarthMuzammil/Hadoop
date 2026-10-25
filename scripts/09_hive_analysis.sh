#!/usr/bin/env bash
# Builds the Hive tables over the MapReduce output and runs the analysis queries.
# Each query's result is saved as results/<query>.tsv (input for the charts).
#   usage: 09_hive_analysis.sh [HDFS_OUTPUT_DIR]   (default /wikitrend/out)
set -euo pipefail
source "$(dirname "$0")/env.sh"
OUT="${1:-$HDFS_OUT}"
UDF_JAR="$PROJECT_DIR/hive/wikitrend-udf.jar"
RESULTS="$PROJECT_DIR/results"
mkdir -p "$RESULTS"

[ -f "$UDF_JAR" ] || "$PROJECT_DIR/hive/build_udf.sh"

# The embedded Derby metastore lives in ~/hive_metastore; run Hive from there
cd "$HOME/hive_metastore"

echo ">> Creating tables over $OUT"
hive --hivevar OUT="$OUT" -f "$PROJECT_DIR/hive/01_create_tables.hql" 2>&1 | grep -vE "^(SLF4J|Hive Session ID|Logging initialized)" | tail -40

for q in "$PROJECT_DIR"/hive/queries/q*.hql; do
  name=$(basename "$q" .hql)
  echo; echo ">> $name"
  hive -S --hivevar UDF_JAR="$UDF_JAR" -i "$PROJECT_DIR/hive/init.hql" -f "$q" 2>/dev/null > "$RESULTS/$name.tsv"
  head -12 "$RESULTS/$name.tsv" | cut -c1-160
done
echo; echo ">> Results saved in $RESULTS"
