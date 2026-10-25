#!/usr/bin/env bash
source "$(dirname "$0")/env.sh"
mapred --daemon stop historyserver
yarn --daemon stop nodemanager
yarn --daemon stop resourcemanager
hdfs --daemon stop datanode
hdfs --daemon stop namenode
