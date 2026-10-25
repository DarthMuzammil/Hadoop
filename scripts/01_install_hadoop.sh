#!/usr/bin/env bash
# One-time setup of a single-node Hadoop 3.3.6 cluster on Ubuntu (run as your normal user, not root).
set -euo pipefail
source "$(dirname "$0")/env.sh"

echo ">> Installing Java 8, Maven, curl and Python plotting libs"
sudo apt-get update -y
sudo apt-get install -y openjdk-8-jdk-headless maven wget curl python3-matplotlib

if [ ! -d "$HADOOP_HOME" ]; then
  echo ">> Downloading Hadoop 3.3.6 (~700 MB)"
  wget -c -P "$HOME" https://archive.apache.org/dist/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz
  tar -xzf "$HOME/hadoop-3.3.6.tar.gz" -C "$HOME"
  ln -sfn "$HOME/hadoop-3.3.6" "$HADOOP_HOME"
fi

echo ">> Installing project configuration into $HADOOP_CONF_DIR"
cp "$PROJECT_DIR"/conf/*.xml "$HADOOP_CONF_DIR/"
grep -q "^export JAVA_HOME=$JAVA_HOME" "$HADOOP_CONF_DIR/hadoop-env.sh" \
  || echo "export JAVA_HOME=$JAVA_HOME" >> "$HADOOP_CONF_DIR/hadoop-env.sh"

if ! grep -q "WikiTrend Hadoop env" "$HOME/.bashrc"; then
  cat >> "$HOME/.bashrc" <<RC
# WikiTrend Hadoop env
export JAVA_HOME=$JAVA_HOME
export HADOOP_HOME=$HADOOP_HOME
export HIVE_HOME=$HIVE_HOME
export PATH=\$HADOOP_HOME/bin:\$HADOOP_HOME/sbin:\$HIVE_HOME/bin:\$PATH
RC
fi

if [ ! -d "$HOME/hadoop_data/namenode/current" ]; then
  echo ">> Formatting the NameNode (first run only)"
  hdfs namenode -format -nonInteractive
fi

echo ">> Building the MapReduce jar"
(cd "$PROJECT_DIR" && mvn -q -B package)
echo ">> Done. Open a new terminal (or 'source ~/.bashrc') and run scripts/02_start_hadoop.sh"
