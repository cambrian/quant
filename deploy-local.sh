#!/bin/bash
set -e

if [ -z "$1" ]
  then
    echo "Script argument expected."
    exit 1
fi

INPUT_FILE=${2:-/dev/null}
python3 scripts/local_spark.py $1 $INPUT_FILE
