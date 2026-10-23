#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build, check and package the whole worked example (guide 5) in one go.

    python3 run_example.py OUT_DIR

Creates OUT_DIR/example-room-1.0.0/ (the delivery package) and the profile used, runs every
checker on it and ends with `build_package.py verify`. Exits non-zero if anything fails.

Requires: pip install ifcopenshell numpy pillow   (jsonschema is optional)
"""
import csv
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
PY = sys.executable
out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "example-out")
pkg = os.path.join(out, "example-room-1.0.0")
os.makedirs(pkg, exist_ok=True)


def run(script, *args, allow_fail=False):
    p = subprocess.run([PY, os.path.join(HERE, script), *args], capture_output=True, text=True)
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    if p.returncode and not allow_fail:
        sys.exit("FAILED: %s %s" % (script, " ".join(args)))
    return p.returncode


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")


# 1. the profiles: the package is checked against the default profile; the master is then renamed and checked against the strict example
strict_path = os.path.join(ROOT, "profiles", "example-strict.json")

# 2. the models and the texture set
run("make_sample.py", pkg)
run("make_sample_texture_set.py", pkg)
run("make_sample_item.py", pkg)

# 3. the finish schedule: one entry for every (class, colour, opacity) key the checker found
keys = [("IfcWall", "#d9d2c3", 1.0, "room walls", {"all": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.55, "normalScale": 0.6}}),
        ("IfcSlab", "#c9c4b8", 1.0, "floor slab", {"top": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.25},
                                                    "side": {"set": "plaster_example"}, "bottom": {"set": "plaster_example"}}),
        ("IfcSlab", "#e8e4da", 1.0, "roof slab (ceiling underneath)", {"top": {"set": "plaster_example"}, "side": {"set": "plaster_example"},
                                                                       "bottom": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.2}}),
        ("IfcDoor", "#977353", 1.0, "timber door leaf", {"all": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.9}}),
        ("IfcFurnishingElement", "#ccbba0", 1.0, "oak work table", {"all": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.8}}),
        ("IfcCovering", "#8c6f4e", 1.0, "timber wall covering", {"all": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.9}}),
        ("IfcLightFixture", "#3d4348", 1.0, "luminaire housing", {"all": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.9}})]
mats = [{"key": {"class": c, "colour": col, "opacity": op}, "role": role, "usedBy": "example room", "faces": faces} for c, col, op, role, faces in keys]
mats.append({"key": {"class": "IfcWindow", "colour": "#91c8d0", "opacity": 0.45}, "role": "window glass", "usedBy": "example room",
             "glass": {"fresnelAlpha": 0.5, "smudgeRough": 0.4}})
mats.append({"key": {"class": "IfcLightFixture", "colour": "#fff0cf", "opacity": 1.0}, "role": "luminaire lens", "usedBy": "example room",
             "keep": True, "reason": "emissive lens: the consumer supplies the glow"})
sched = {"format": "finish-schedule/1", "delivery": "example-room-1.0.0", "version": "1.0.0", "materials": mats,
         "floors": [{"id": "floor-work", "where": {"occupant": "Example Occupant"}, "finish": {"set": "plaster_example", "tint": "#b08d63", "tintStrength": 0.6},
                     "note": "oak plank floor intent; the consumer picks its own timber set"}],
         "libraries": [{"name": "plaster_example", "version": "1.0.0"}]}
write_json(os.path.join(pkg, "finishes", "finish-schedule.json"), sched)
with open(os.path.join(pkg, "finishes", "SOURCES.csv"), "w", newline="") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["asset", "type", "source", "licence", "notes"])
    w.writerow(["finishes/textures/plaster_example", "texture set", "procedural: tools/make_sample_texture_set.py, seed 7", "free to reuse (example)", "no input images"])
os.makedirs(os.path.join(pkg, "notes"), exist_ok=True)
with open(os.path.join(pkg, "notes", "changes.md"), "w", newline="\n") as fh:
    fh.write("# Changes\n\n## 1.0.0\n\nFirst delivery: one room, one door, one window, one table, one wall covering, one luminaire.\n")

write_json(os.path.join(pkg, "finishes", "library.json"), {
    "format": "material-library/1", "name": "example-finishes", "version": "1.0.0", "description": "one plaster set and the finish schedule of the example room",
    "sets": [{"name": "plaster_example", "version": "1.0.0", "path": "textures/plaster_example"}], "schedule": "finish-schedule.json"})
write_json(os.path.join(pkg, "tables", "building.json"), {
    "format": "building-metadata/1", "building": {"id": "B-EXAMPLE", "name": "Example building", "layer": "interim"},
    "frame": {"units": "metres", "axes": "+X forward, +Y left, +Z up", "levelOffsetMetres": 12.0},
    "ifc": {"path": "ifc/example-room-master.ifc", "schema": "IFC4", "entityNumberStart": 700001},
    "levels": [{"name": "Example building - ground / +0 m", "elevationMetres": 0.0, "rooms": 1}],
    "occupants": ["Example Occupant"], "roomIdPrefix": "EX"})

# 4. the checks, with reports inside the package
os.makedirs(os.path.join(pkg, "reports"), exist_ok=True)
master = os.path.join(pkg, "ifc", "example-room-master.ifc")
run("check_ifc.py", master, "--finish-schedule", os.path.join(pkg, "finishes", "finish-schedule.json"),
    "--report", os.path.join(pkg, "reports", "check_ifc.json"))
run("check_texture_set.py", os.path.join(pkg, "finishes", "textures", "plaster_example"), "--report", os.path.join(pkg, "reports", "check_texture_set.json"))
run("check_item.py", os.path.join(pkg, "items", "table.work.1600"), "--report", os.path.join(pkg, "reports", "check_item-table.work.1600.json"))

# 5. the manifest
with open(os.path.join(pkg, "reports", "check_ifc.json")) as fh:
    counts = json.load(fh)["counts"]
meta = {
    "delivery": {"id": "example-room", "title": "Worked example: one room", "version": "1.0.0", "created": "2026-10-22T00:00:00Z",
                 "supersedes": None, "kind": ["building", "materials", "furniture"]},
    "author": {"organisation": "Example organisation", "role": "example author", "contact": "example role mailbox"},
    "profile": {"name": "default", "version": "1.0.0"},
    "frame": {"units": "metres", "axes": "+X forward, +Y left, +Z up", "levelOffsetMetres": 12.0, "localZero": "finished floor of the lowest level"},
    "ifc": {"schema": "IFC4", "entityNumberStart": 700001}, "counts": counts,
    "provenance": [
        {"asset": "ifc/example-room-master.ifc", "type": "ifc-model", "source": "original: tools/make_sample.py", "author": "Example organisation", "licence": "free to reuse (example)"},
        {"asset": "finishes/textures/plaster_example", "type": "texture-set", "source": "procedural: tools/make_sample_texture_set.py, seed 7", "author": "Example organisation", "licence": "free to reuse (example)"},
        {"asset": "items/table.work.1600", "type": "item", "source": "original: tools/make_sample_item.py", "author": "Example organisation", "licence": "free to reuse (example)"}],
    "licence": {"statement": "Everything in this package is an example and is free to reuse."},
    "checks": {"tool": "check_ifc.py", "toolVersion": "2.1.0", "report": "reports/check_ifc.json", "result": "pass"}}
meta_path = os.path.join(out, "package-meta.json")
write_json(meta_path, meta)
run("build_package.py", "init", pkg, meta_path)
run("build_package.py", "verify", pkg)
run("check_all.py", pkg)
# the same master under a strict consumer profile: rename the declaration properties, then check
strict_master = os.path.join(out, "master-strict.ifc")
run("map_properties.py", master, strict_master, "--mapping", strict_path)
run("check_ifc.py", strict_master, "--profile", strict_path)
print("example package ready:", pkg)
