#!/bin/bash
set -e

# Usage:
# 1. Set up your AWS CLI credentials.
# 2. Run `./spark.sh SCRIPT [INPUT_FILE]`.

if [ -z "$1" ]
  then
    echo "Script argument expected."
    exit 1
fi

INPUT_FILE=${2:-/dev/null}
export PYTHONPATH=$PYTHONPATH:.
python3 $1 --conf-path mrjob.conf -r emr $INPUT_FILE
