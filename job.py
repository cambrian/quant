"""Generates a job from a job function and boilerplate."""
import os
import sys

boilerplate = open("scripts/remote/base.py").readlines()
script = open(sys.argv[1]).readlines()
name = os.path.splitext(os.path.basename(sys.argv[1]))[0]
result = ['"""Generated job script."""', "\n"] + boilerplate[1:4] + script + boilerplate[6:]
result = [line.replace("REPLACE_NAME", name) for line in result]
open("generated.py", "w").writelines(result)
