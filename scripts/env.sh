#!/usr/bin/env bash
# Common settings sourced by every script. Override any of these by exporting them first.
# Hadoop 3.3 + Hive 3.1 need Java 8 (Hive 3 does not run on Java 11+), so this is pinned on purpose.
export JAVA_HOME="${WIKITREND_JAVA_HOME:-/usr/lib/jvm/java-8-openjdk-amd64}"
export HADOOP_HOME="${HADOOP_HOME:-$HOME/hadoop}"
export HADOOP_CONF_DIR="${HADOOP_CONF_DIR:-$HADOOP_HOME/etc/hadoop}"
export HIVE_HOME="${HIVE_HOME:-$HOME/hive}"
export PATH="$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$HIVE_HOME/bin:$PATH"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROJECT_DIR
export JAR="$PROJECT_DIR/target/wikitrend.jar"

# Dataset: 30 consecutive hours of Wikipedia hourly pageviews, 2022-09-07 18:00 .. 2022-09-08 23:00 UTC
# (8 Sep 2022 = death of Queen Elizabeth II). The 6 hours of 7 Sep give the first hours of 8 Sep a baseline.
export DATA_START="${DATA_START:-2022-09-07 18:00}"
export DATA_HOURS="${DATA_HOURS:-30}"
export LOCAL_DATA="${LOCAL_DATA:-$HOME/wikidata/raw}"

# HDFS layout
export HDFS_BASE="${HDFS_BASE:-/wikitrend}"
export HDFS_RAW="$HDFS_BASE/raw"          # the >= 4 GB dataset (uncompressed hourly files)
export HDFS_OUT="$HDFS_BASE/out"          # batch results: agg/ spikes/ top/ (partitioned by hour=)
export HDFS_LANDING="$HDFS_BASE/landing"  # real-time: new hourly files arrive here
export HDFS_LIVE="$HDFS_BASE/live"        # real-time results
export HDFS_ARCHIVE="$HDFS_BASE/archive"  # real-time: processed files move here
