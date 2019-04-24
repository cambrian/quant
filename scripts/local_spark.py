# NOTE: Keep me at the top. (Sets up the module environment to run this script.)
import setup  # isort:skip, pylint: disable=import-error

import os
import sys
from importlib.machinery import SourceFileLoader

from pyspark import SparkContext

# Assumes you have JDK 1.8 as installed in the setup script.
os.environ["PYSPARK_PYTHON"] = "python3"
os.environ["JAVA_HOME"] = "/Library/Java/JavaVirtualMachines/adoptopenjdk-8.jdk/Contents/Home"

if len(sys.argv) < 2:
    print("Script argument expected.")
    sys.exit(1)

if len(sys.argv) < 3:
    input_path = "/dev/null"
else:
    input_path = sys.argv[2]

# Extract job name and job function from script file.
name = os.path.splitext(os.path.basename(sys.argv[1]))[0]
job = getattr(SourceFileLoader(name, sys.argv[1]).load_module(name), "job")

# Run the job locally.
sc = SparkContext("local", name)
print(job(sc, input_path, os.getcwd()))
sc.stop()
