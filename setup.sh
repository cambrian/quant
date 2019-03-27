# Try to ensure use of the Python 3 pip.
if [ -x "$(command -v pip3)" ]; then
    pip3 install -r requirements.txt
else
    pip install -r requirements.txt
fi

git config filter.nbstripout.clean 'nbstripout'
git config filter.nbstripout.smudge cat
git config filter.nbstripout.required true
git config diff.ipynb.textconv 'nbstripout -t'
