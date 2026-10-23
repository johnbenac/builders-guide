#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run one tool of the guide set from anywhere.

    python3 scripts/run_tool.py TOOL [ARGS...]      for example: run_tool.py check_all /path/to/master.ifc --json

TOOL is the name of a script in the set's tools/ folder, with or without .py. The set's root folder is found from the
environment variable BUILDERS_GUIDE_ROOT, or by walking up from this file until tools/check_all.py is found. The tool's
exit code is passed through (0 pass, 1 REQUIRED failure, 2 wrong command line, 3 unreadable input).
"""
import os
import subprocess
import sys


def find_root():
    env = os.environ.get("BUILDERS_GUIDE_ROOT")
    if env and os.path.exists(os.path.join(env, "tools", "check_all.py")):
        return env
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.exists(os.path.join(d, "tools", "check_all.py")):
            return d
        d = os.path.dirname(d)
    sys.exit("cannot find the guide set: set BUILDERS_GUIDE_ROOT to its top folder (the one that contains tools/check_all.py)")


if len(sys.argv) < 2:
    sys.exit(__doc__)
tool = sys.argv[1] if sys.argv[1].endswith(".py") else sys.argv[1] + ".py"
root = find_root()
path = os.path.join(root, "tools", tool)
if not os.path.exists(path):
    sys.exit("no such tool: %s" % path)
sys.exit(subprocess.call([sys.executable, path, *sys.argv[2:]]))
