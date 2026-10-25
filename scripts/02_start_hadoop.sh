#!/usr/bin/env bash
# Start HDFS + YARN + JobHistory daemons. Uses --daemon (no passwordless SSH needed).
set -euo pipefail
source "$(dirname "$0")/env.sh"

hdfs --daemon start namenode
hdfs --daemon start datanode
yarn --daemon start resourcemanager
yarn --daemon start nodemanager
mapred --daemon start historyserver
hdfs dfsadmin -safemode wait
sleep 3
jps
echo
echo "NameNode UI : http://localhost:9870"
echo "YARN UI     : http://localhost:8088"
echo "JobHistory  : http://localhost:19888"
