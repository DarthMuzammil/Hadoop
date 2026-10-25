#!/usr/bin/env bash
# Compiles the Hive UDFs against the installed Hive/Hadoop jars -> hive/wikitrend-udf.jar
set -euo pipefail
source "$(dirname "$0")/../scripts/env.sh"
cd "$(dirname "$0")"
rm -rf build && mkdir build
"$JAVA_HOME/bin/javac" -source 8 -target 8 -nowarn -d build \
  -cp "$HIVE_HOME/lib/hive-exec-3.1.3.jar:$(hadoop classpath)" udf/com/wikitrend/hive/*.java
"$JAVA_HOME/bin/jar" cf wikitrend-udf.jar -C build .
rm -rf build
echo ">> Built $(pwd)/wikitrend-udf.jar"
