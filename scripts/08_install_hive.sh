#!/usr/bin/env bash
# One-time setup of Apache Hive 3.1.3 on top of the Hadoop installation (embedded Derby metastore).
set -euo pipefail
source "$(dirname "$0")/env.sh"

if [ ! -d "$HIVE_HOME" ]; then
  echo ">> Downloading Hive 3.1.3 (~320 MB)"
  wget -c -P "$HOME" https://archive.apache.org/dist/hive/hive-3.1.3/apache-hive-3.1.3-bin.tar.gz
  tar -xzf "$HOME/apache-hive-3.1.3-bin.tar.gz" -C "$HOME"
  ln -sfn "$HOME/apache-hive-3.1.3-bin" "$HIVE_HOME"
fi

# Known Hive 3.1.3 + Hadoop 3.3 issue: Hive ships guava 19, Hadoop needs guava 27
# ("NoSuchMethodError: com.google.common.base.Preconditions.checkArgument"). Use Hadoop's guava.
if ls "$HIVE_HOME"/lib/guava-19*.jar >/dev/null 2>&1; then
  echo ">> Replacing Hive's guava-19 with Hadoop's guava-27"
  rm -f "$HIVE_HOME"/lib/guava-19*.jar
  cp "$HADOOP_HOME"/share/hadoop/common/lib/guava-27*.jar "$HIVE_HOME/lib/"
fi
# Duplicate SLF4J binding warning noise
rm -f "$HIVE_HOME"/lib/log4j-slf4j-impl-*.jar

sed "s|__HOME__|$HOME|g" "$PROJECT_DIR/conf/hive-site.xml" > "$HIVE_HOME/conf/hive-site.xml"

hdfs dfs -mkdir -p /user/hive/warehouse /tmp
hdfs dfs -chmod g+w /user/hive/warehouse /tmp

if [ ! -d "$HOME/hive_metastore/metastore_db" ]; then
  echo ">> Initialising the metastore schema"
  mkdir -p "$HOME/hive_metastore"
  (cd "$HOME/hive_metastore" && schematool -dbType derby -initSchema)
fi
echo ">> Hive ready: $(hive --version 2>/dev/null | head -1)"
