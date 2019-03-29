#!/bin/bash

# Try to ensure use of the Python 3 pip.
if [ -x "$(command -v pip3)" ]; then
    pip3 install -r requirements.txt
else
    pip install -r requirements.txt
fi

# Grab test exchange data from S3
python3 -m pip install awscli --upgrade --user
mkdir -p research/data/test
aws s3 cp --recursive s3://cambrianexchangedata/data/test/ research/data/test

git config filter.nbstripout.clean 'nbstripout'
git config filter.nbstripout.smudge cat
git config filter.nbstripout.required true
git config diff.ipynb.textconv 'nbstripout -t'
