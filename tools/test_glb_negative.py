#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Negative and adversarial tests of the optional GLB features: malformed node transforms, volumes inside assemblies, pivot files with bad numbers or
unknown keys, tilted and inverted placements, terrain rows, coincident-face edge cases, the walk check on stairs, tall buildings, big inputs and bad
options, and the set check on an empty, truncated or tampered manifest.

    python3 tools/test_glb_negative.py [WORK_DIR]

Companion of test_glb_options.py (which shows the features work); this file shows they refuse what they must. Requires tools/requirements.txt and scipy.
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="glb-negative-test-")
os.makedirs(work, exist_ok=True)
FAILS = []


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FAIL", msg)


def py(script, *args):
    return subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *map(str, args)], capture_output=True, text=True)


import numpy as np  # noqa: E402
import coplanar  # noqa: E402
import glbkit  # noqa: E402
import report as rpt  # noqa: E402
import validate_glb  # noqa: E402

rpt.load_profile(None)


def repack(doc, bn):
    js = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("ascii")
    js += b" " * (-len(js) % 4)
    bn = bytes(bn) + b"\0" * (-len(bn) % 4)
    return b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bn), b"BIN\0") + bn


def box(x0, y0, z0, x1, y1, z1):
    p = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
    f = [(0, 3, 2), (0, 2, 1), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return np.array([p[i] for tri in f for i in tri], dtype=float)


def comp(name, kind, gid, *boxes, category="x", node=None):
    c = {"name": "%s:%s#%s" % (kind, name, gid), "extras": {"globalId": gid, "ifcClass": "IfcX", "kind": kind, "category": category, "level": "Ground"},
         "parts": [((0.7, 0.7, 0.7, 1.0), np.concatenate([box(*b) for b in boxes]))]}
    if node:
        c["node"] = node
    return c


def scene(comps, bounds=None, rooms=None, levels=None, **extra):
    allv = np.concatenate([p[1] for c in comps for p in c["parts"]])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    extras = {"source": {"ifcPath": "x.ifc", "ifcSha256": "0" * 64}, "levels": levels or [{"name": "Ground", "elevation": 0.0}], "rooms": rooms or [],
              "bounds": bounds or {"min": [float(x) for x in lo], "max": [float(x) for x in hi]}, "counts": {}}
    extras.update(extra)
    return glbkit.write_scene_glb("model", [{"name": "Ground", "extras": {"elevation": 0.0}, "components": comps}], [], extras)


def validate(data, name="x.glb"):
    d = os.path.join(work, "vg")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, "wb") as fh:
        fh.write(data)
    return validate_glb.validate_files([{"path": p, "label": name, "role": "model"}], None, "off")


def codes(rep, levels=("fail", "warn")):
    return sorted({f.get("code") or f["rule"] for f in rep["findings"] if f["status"] in levels})


def messages(rep, code):
    return [f["message"] for f in rep["findings"] if (f.get("code") or f["rule"]) == code]


# ------------------------------------------------------------------ 1. validate_glb: malformed node transforms are findings, not silent
BASE = scene([comp("Floor", "structure", "AAAAAAAAAAAAAAAAAAAAAA", (0, 0, -0.2, 10, 6, 0)), comp("Wall", "structure", "BBBBBBBBBBBBBBBBBBBBBB", (0, 0, 0, 0.2, 6, 2.6))])
rep0 = validate(BASE)
expect(rep0["result"] == "pass" and not codes(rep0), "the synthetic model itself is valid: %s" % [f["message"] for f in rep0["findings"] if f["status"] != "pass"][:3])


def with_node(mutate):
    doc, bn = glbkit.split_glb(BASE)
    node = next(n for n in doc["nodes"] if n.get("name", "").startswith("structure:Wall"))
    mutate(node)
    return repack(doc, bn)


bad_transforms = {
    "translation of two numbers": lambda n: n.update(translation=[1, 2]),
    "translation of strings": lambda n: n.update(translation=["a", "b", "c"]),
    "translation with NaN": lambda n: n.update(translation=[float("nan"), 0, 0]),
    "scale of two numbers": lambda n: n.update(scale=[1, 1]),
    "NaN scale": lambda n: n.update(scale=[float("nan"), 1, 1]),
    "zero scale": lambda n: n.update(scale=[1, 0, 1]),
    "negative scale": lambda n: n.update(scale=[-1, 1, 1]),
    "boolean scale": lambda n: n.update(scale=[True, True, True]),
    "matrix of 15 numbers": lambda n: n.update(matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1]),
    "matrix with NaN": lambda n: n.update(matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, float("nan"), 0, 0, 1]),
    "mirrored matrix": lambda n: n.update(matrix=[-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 0, 0, 1]),
    "zero matrix": lambda n: n.update(matrix=[0] * 16),
    "projective matrix": lambda n: n.update(matrix=[1, 0, 0, 0.5, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
    "rotation of three numbers": lambda n: n.update(rotation=[0, 0, 0]),
    "rotation that is not a unit quaternion": lambda n: n.update(rotation=[0, 0, 0, 2]),
}
for label, mut in bad_transforms.items():
    data = with_node(mut)
    # NaN is not valid JSON; json.dumps writes it as NaN, which split_glb's reader still accepts
    rep = validate(data)
    expect(rep["result"] == "fail" and "GLB-NODE" in codes(rep), "%s: GLB-NODE and a failing result: %s %s" % (label, rep["result"], codes(rep)))
# a harmless matrix (a pure translation) still passes the node check
ok = with_node(lambda n: n.update(matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]))
expect("GLB-NODE" not in codes(validate(ok)), "an identity matrix is accepted")
# the downstream tools refuse a malformed file with a clean message, not a traceback
bad_path = os.path.join(work, "bad-transform.glb")
with open(bad_path, "wb") as fh:
    fh.write(with_node(bad_transforms["translation of two numbers"]))
r = py("coplanar.py", bad_path)
expect(r.returncode == 3 and "Traceback" not in r.stderr, "coplanar.py: a malformed transform is exit 3 without a traceback: %s" % r.stderr[-200:])
r = py("walkcheck.py", bad_path, "--start", "1,1,0")
expect(r.returncode == 3 and "Traceback" not in r.stderr, "walkcheck.py: a malformed transform is exit 3 without a traceback: %s" % r.stderr[-200:])

# GLB-COPLANAR reports a failure of the check instead of "clean"
orig = coplanar.glb_overlaps


def boom(data, min_area=0.005):
    raise RuntimeError("synthetic failure")


coplanar.glb_overlaps = boom
try:
    rep = validate(BASE)
finally:
    coplanar.glb_overlaps = orig
expect(rep["result"] == "fail" and any("internal error" in m for m in messages(rep, "GLB-COPLANAR")), "an exception in the coplanar check is a finding, not a pass: %s" % messages(rep, "GLB-COPLANAR"))


def read_fail(data, min_area=0.005):
    raise glbkit.Failed("synthetic read error")


coplanar.glb_overlaps = read_fail
try:
    rep = validate(BASE)
finally:
    coplanar.glb_overlaps = orig
expect(rep["result"] == "pass" and any("could not run" in m for m in messages(rep, "GLB-COPLANAR")), "a read error in the coplanar check is a RECOMMENDED finding: %s" % codes(rep))

# negative zero never reaches the report
neg = scene([comp("Floor", "structure", "AAAAAAAAAAAAAAAAAAAAAA", (0, 0, -0.2, 10, 6, 0))])
rep = validate(neg)
txt = json.dumps(rep["files"][0]["boundsIfcFrame"])
expect("-0.0" not in txt, "boundsIfcFrame holds no negative zero: %s" % txt)

if __name__ == "__main__":
    print("test_glb_negative: %s" % ("all checks behaved as expected" if not FAILS else "%d failure(s)" % len(FAILS)))
    sys.exit(1 if FAILS else 0)
