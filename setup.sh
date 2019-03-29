#!/bin/bash
python3 -m pip install -r requirements.txt

# Grab test exchange data from S3.
mkdir -p research/data/test
echo 'Downloading exchange data from S3...'
aws s3 cp --recursive s3://cambrianexchangedata/data/test/ research/data/test
echo 'Done.'

git config filter.nbstripout.clean 'nbstripout'
git config filter.nbstripout.smudge cat
git config filter.nbstripout.required true
git config diff.ipynb.textconv 'nbstripout -t'
