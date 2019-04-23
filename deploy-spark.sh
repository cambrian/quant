#!/bin/bash
set -e

if [ -z "$1" ]
  then
    echo "Script argument expected."
    exit 1
fi

# Security YOLO...
export AWS_ACCESS_KEY_ID=AKIA3CMPUXHLHXWY23PM
export AWS_SECRET_ACCESS_KEY=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

# Archive current master of `quant` as a dependency.
git archive --output quant.zip master

# Generate complete job runner.
python3 job.py $1

INPUT_FILE=${2:-/dev/null}
export PYTHONPATH=$PYTHONPATH:.
python3 generated.py --conf-path mrjob.conf -r emr $INPUT_FILE
rm -f quant.zip
