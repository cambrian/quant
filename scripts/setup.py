"""The `setup` module.

Sets up PYTHONPATH for scripts in this directory. This is useful for scripts to import from our
modules but still be runnable from anywhere.

EITHER:

# Setup the module environment to run this script.
import setup  # isort:skip, pylint: disable=import-error

OR:

# Setup the module environment to run this script.
from setup import ROOT_DIRECTORY  # isort:skip, pylint: disable=import-error

"""

import os
import sys

ROOT_DIRECTORY = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(ROOT_DIRECTORY)
