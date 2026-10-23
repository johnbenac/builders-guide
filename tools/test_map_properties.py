#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test of map_properties.py: neutral to consumer names and back is byte-identical, and the checker reads the mapped file.

    python3 test_map_properties.py [WORK_DIR]
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="maptest-")
py = sys.executable


def run(*a, ok=True):
    p = subprocess.run([py, *a], capture_output=True, text=True)
    if ok and p.returncode:
        sys.exit("FAILED: %s\n%s%s" % (a, p.stdout, p.stderr))
    return p


run(os.path.join(HERE, "make_sample.py"), work)
src = os.path.join(work, "ifc", "example-room-master.ifc")
names = ["LuminaireId", "LightPosition", "LightAim", "LightType", "LightEnergy", "LightRangeM", "LightSpotDeg", "LightColor",
         "LuminaireMount", "LightFadeBeginM", "LightFadeLengthM", "LuminaireTarget"]
mp = os.path.join(work, "mapping.json")
with open(mp, "w") as fh:
    json.dump({"propertyNames": {n: "Host_" + n for n in names}}, fh)
mapped, back = os.path.join(work, "mapped.ifc"), os.path.join(work, "back.ifc")
run(os.path.join(HERE, "map_properties.py"), src, mapped, "--mapping", mp)
run(os.path.join(HERE, "map_properties.py"), mapped, back, "--mapping", mp, "--reverse")
with open(src, "rb") as a, open(back, "rb") as b:
    assert a.read() == b.read(), "round trip is not byte-identical"
with open(mapped, "rb") as fh:
    t = fh.read()
assert b"'Host_LuminaireId'" in t and b"'LuminaireId'" not in t
def profile(path, with_names):
    p = {"format": "profile/1", "name": "maptest", "version": "1.0.0", "frame": {"levelOffsetMetres": 12.0},
         "extensions": {"luminaires": {"enabled": True}}}
    if with_names:
        p["propertyNames"] = {n: "Host_" + n for n in names}
    with open(path, "w") as fh:
        json.dump(p, fh)
    return path


bare = run(os.path.join(HERE, "check_ifc.py"), mapped, "--profile", profile(os.path.join(work, "p-bare.json"), False), ok=False)
assert bare.returncode == 1, "without the names the checker should not find the renamed properties"
good = run(os.path.join(HERE, "check_ifc.py"), mapped, "--profile", profile(os.path.join(work, "p-names.json"), True))
assert "PASS" in good.stdout
print("map_properties: round trip identical, mapped file read through the profile's propertyNames")
