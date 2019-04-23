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

# Archive current master of `quant`.
git archive --output quant.zip master

# Generate complete job runner.
python3 job.py $1

INPUT_FILE=${2:-/dev/null}
export PYTHONPATH=$PYTHONPATH:.
python3 generated.py --conf-path mrjob.conf -r emr $INPUT_FILE
rm -f quant.zip
