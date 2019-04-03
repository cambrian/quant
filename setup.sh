#!/bin/bash
pip3 install -r requirements.txt --upgrade

# TODO: Resolve test data discussion.
# Grab test exchange data from S3.
# mkdir -p research/data/test
# echo 'Downloading exchange data from S3...'
# aws s3 cp --no-sign-request --recursive s3://cambrianexchangedata/data/test/ research/data/test
# echo 'Done.'

git config filter.nbstripout.clean 'nbstripout'
git config filter.nbstripout.smudge cat
git config filter.nbstripout.required true
git config diff.ipynb.textconv 'nbstripout -t'
