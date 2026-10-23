#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test the three worked fixtures (tools/make_fixtures.py), the terrain chain on them (building rotation, several ground-contact
levels), the preview, and every rule that the fixtures were added to exercise, each broken in turn.

    python3 test_fixtures.py [WORK_DIR]

Requires: pip install ifcopenshell numpy pillow scipy shapely (matplotlib for the preview check)
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np
import ifcopenshell
import ifcopenshell.geom

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_fixtures  # noqa: E402
import terrain_lib as tl  # noqa: E402

work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="fixtures-test-")
os.makedirs(work, exist_ok=True)
PROFILE = os.path.join(work, "terrain-profile.json")
with open(PROFILE, "w") as fh:
    json.dump({"format": "profile/1", "name": "fixture-terrain", "version": "1.0.0",
               "extensions": {"terrain": {"enabled": True, "crsName": "SYNTHETIC-SITE"}}}, fh)


def tool(name, *args, expect=0):
    p = subprocess.run([sys.executable, os.path.join(HERE, name), *map(str, args)], capture_output=True, text=True)
    assert p.returncode == expect, "%s exited %d, expected %d: %s" % (name, p.returncode, expect, (p.stderr or p.stdout)[-500:])
    return p


def check(path, profile=None):
    rep = path + ".report.json"
    cmd = [sys.executable, os.path.join(HERE, "check_ifc.py"), path, "--report", rep]
    if profile:
        cmd += ["--profile", profile]
    p = subprocess.run(cmd, capture_output=True, text=True)
    with open(rep) as fh:
        return p.returncode, json.load(fh)


def open_findings(rep):
    return [f for f in rep["findings"] if f["status"] in ("fail", "warn")]


def expect(name, rule, path, profile=None):
    rc, rep = check(path, profile)
    hit = [f for f in rep["findings"] if f["rule"] == rule and f["status"] in ("fail", "warn")]
    ok = bool(hit) and (rc == 1 or hit[0]["level"] == "RECOMMENDED")
    print("%-26s expects %-5s -> %s" % (name, rule, "caught" if ok else "NOT CAUGHT"))
    if not ok:
        print(json.dumps(rep["findings"], indent=1))
        sys.exit(1)


def mutate(src, name, rule, fn, profile=None):
    m = ifcopenshell.open(src)
    fn(m)
    out = os.path.join(work, "broken-%s.ifc" % name)
    m.write(out)
    expect(name, rule, out, profile)


def named(m, cls, name):
    return [e for e in m.by_type(cls) if (e.Name or "").startswith(name)][0]


def prop(m, name, value=None):
    ps = [p for p in m.by_type("IfcPropertySingleValue") if p.Name == name and (value is None or p.NominalValue.wrappedValue == value)]
    return ps[0]


# ------------------------------------------------------------------ 1. the fixtures build and pass cleanly
masters, places = {}, {}
for n in make_fixtures.FIXTURES:
    masters[n], places[n] = make_fixtures.build(n, work)
    rc, rep = check(masters[n])
    assert rc == 0 and not open_findings(rep), "%s must pass without warnings: %s" % (n, open_findings(rep))
    print("%-16s PASS (%s)" % (n, ", ".join("%s %s" % (v, k) for k, v in rep["counts"].items() if k in ("levels", "rooms", "doors", "windows", "triangles"))))
    again = make_fixtures.FIXTURES[n]()[0].write(os.path.join(work, "again", n), "master.ifc")
    assert open(again, "rb").read() == open(masters[n], "rb").read(), "%s is not deterministic" % n

# what each fixture is there to show
m = ifcopenshell.open(masters["courtyard"])
battered = [w for w in m.by_type("IfcWall") if w.Representation.Representations[0].Items[0].SweptArea.is_a("IfcArbitraryClosedProfileDef")]
assert len(battered) >= 4, "the courtyard fixture needs battered walls"
assert any(sp.PredefinedType == "EXTERNAL" for sp in m.by_type("IfcSpace")), "the courtyard fixture needs an open-air room"
m = ifcopenshell.open(masters["hillside-block"])
assert len([s for s in m.by_type("IfcBuildingStorey")]) == 2 and len([s for s in m.by_type("IfcFooting")]) == 1
assert len([s for s in m.by_type("IfcSlab") if s.PredefinedType == "ROOF"]) == 2, "the hillside fixture needs a pitched roof of two slabs"
assert any(w.ObjectType == "retaining" for w in m.by_type("IfcWall")), "the hillside fixture needs a retaining wall"
print("fixture features present (battered walls, open-air rooms, footing, pitched roof, retaining wall)")

# ------------------------------------------------------------------ 2. the terrain chain on each fixture
terrain_ifc = {}
for n, pl in places.items():
    d = os.path.join(work, n)
    req = os.path.join(d, "site-request.json")
    tool("site_request.py", masters[n], "--floor-elevation", pl["floor"], "--origin", *pl["origin"], "--azimuth", pl["azimuth"],
         "--profile", PROFILE, "--out", req)
    tool("make_sample_terrain.py", d, "--request", req, "--height-at-origin", pl["height_at_origin"], "--slope-x", pl["slope_x"],
         "--slope-y", pl["slope_y"], "--pixel-size", 0.5)
    out = os.path.join(d, "ifc", "terrain.ifc")
    tool("terrain_import.py", os.path.join(d, "terrain", "patch.tif"), os.path.join(d, "terrain", "patch.json"), masters[n], "--request", req,
         "--out", out, "--profile", PROFILE)
    rc, rep = check(out, PROFILE)
    assert rc == 0 and not open_findings(rep), "%s with terrain must pass: %s" % (n, open_findings(rep))
    terrain_ifc[n] = out
    print("%-16s with terrain: PASS" % n)

# the hillside block: two ground-contact levels, turned 30 degrees; the file-frame terrain is the site's ground turned back
pl = places["hillside-block"]
req = json.load(open(os.path.join(work, "hillside-block", "site-request.json")))
assert [lv["elevationMetres"] for lv in req["levels"]] == [0.0, 3.0], "both declared levels must be in the request"
assert abs(req["levels"][1]["finishedFloorElevationMetres"] - 1203.0) < 1e-9
poly = np.array(req["levels"][0]["footprint"]["polygons"][0])          # the lower block is the rectangle 0..10 by 0..6 in the file frame
cx = poly.mean(0)
th = math.radians(30)
want = np.array([500 + math.cos(th) * 5 - math.sin(th) * 3, 200 + math.sin(th) * 5 + math.cos(th) * 3])
assert np.abs(cx - want).max() < 0.5, "the footprint is not turned by the azimuth: %s vs %s" % (cx, want)
rc, rep = check(terrain_ifc["hillside-block"], PROFILE)
assert any(f["rule"] == "B-141" and f["status"] == "pass" and "lower" in f["message"] and "upper" in f["message"] for f in rep["findings"]), "both levels must be ground-contact"
m = ifcopenshell.open(terrain_ifc["hillside-block"])
conv = m.by_type("IfcMapConversion")[0]
assert abs(math.degrees(math.atan2(conv.XAxisOrdinate, conv.XAxisAbscissa)) - 30.0) < 1e-6
settings = ifcopenshell.geom.settings()
settings.set("use-world-coords", True)
t = [e for e in m.by_type("IfcGeographicElement")][0]
sh = ifcopenshell.geom.create_shape(settings, t)
V, F = np.array(sh.geometry.verts).reshape(-1, 3), np.array(sh.geometry.faces).reshape(-1, 3)
pts = np.array([[0.0, 0.0], [10.0, 0.0], [3.0, 12.0], [-2.0, 6.0]])
site = np.column_stack([500 + math.cos(th) * pts[:, 0] - math.sin(th) * pts[:, 1], 200 + math.sin(th) * pts[:, 0] + math.cos(th) * pts[:, 1]])
expected = pl["height_at_origin"] + pl["slope_x"] * (site[:, 0] - 500) + pl["slope_y"] * (site[:, 1] - 200) - pl["floor"]
got = tl.heights_at(V, F, pts)
assert np.abs(got - expected).max() < 1e-4, "terrain heights in the file frame are wrong: %s vs %s" % (got, expected)
print("hillside block: two ground levels, azimuth 30 degrees, file-frame terrain matches the site's ground (max difference %.2g m)" % np.abs(got - expected).max())

# ------------------------------------------------------------------ 3. the preview draws plans and a view
try:
    import matplotlib  # noqa: F401
    pv = os.path.join(work, "preview")
    tool("preview.py", terrain_ifc["hillside-block"], pv)
    names = sorted(os.listdir(pv))
    assert len([x for x in names if x.startswith("plan-")]) == 2 and "iso.png" in names and all(os.path.getsize(os.path.join(pv, x)) > 2000 for x in names)
    print("preview: %d pictures" % len(names))
except ImportError:
    print("matplotlib not installed: preview check skipped")

# ------------------------------------------------------------------ 4. each new rule, broken in turn
tray, court, hill = masters["tray-house"], masters["courtyard"], masters["hillside-block"]


def no_roof(m):
    m.remove(named(m, "IfcSlab", "Roof"))


def overlap(m):
    named(m, "IfcSpace", "Living terrace").ObjectPlacement.RelativePlacement.Location.Coordinates = (0.0, 5.0, 0.0)


def lose_door(m):
    named(m, "IfcDoor", "Door c-w").ObjectPlacement.RelativePlacement.Location.Coordinates = (100.0, 100.0, 0.0)


def no_well(m):
    op = named(m, "IfcOpeningElement", "Opening hole/stair")
    for rel in list(op.VoidsElements):
        m.remove(rel)


def window_below(m):
    named(m, "IfcWindow", "Window W0").ObjectPlacement.RelativePlacement.Location.Coordinates = (0.0, 0.0, -2.0)


def enclosed_terrace(m):
    prop(m, "Enclosed", False).NominalValue = m.create_entity("IfcBoolean", wrappedValue=True)


mutate(tray, "no-roof", "B-54", no_roof)
mutate(tray, "rooms-overlap", "B-30", overlap)
mutate(court, "door-lost", "B-47", lose_door)
mutate(tray, "no-stair-well", "B-61", no_well)
mutate(hill, "window-below-floor", "B-142", window_below)
mutate(tray, "terrace-enclosed", "B-143", enclosed_terrace)


def bad_axis(m):
    m.by_type("IfcMapConversion")[0].XAxisAbscissa = 2.0


mutate(terrain_ifc["hillside-block"], "axis-not-unit", "B-133", bad_axis, PROFILE)

# a level that sits on the ground but is not declared (B-141): undeclare the upper level, then ground it with flat terrain at its floor
m = ifcopenshell.open(hill)
for p in [p for p in m.by_type("IfcPropertySingleValue") if p.Name == "GroundContact"]:
    p.Name = "Anchored"
undeclared = os.path.join(work, "hill-undeclared.ifc")
m.write(undeclared)
d = os.path.join(work, "undeclared")
req2 = os.path.join(d, "req.json")
os.makedirs(d, exist_ok=True)
tool("site_request.py", undeclared, "--floor-elevation", 1200.0, "--origin", 500, 200, "--azimuth", 30, "--profile", PROFILE, "--out", req2)
assert len(json.load(open(req2))["levels"]) == 1, "with no declaration only the lowest level is a ground-contact level"
tool("make_sample_terrain.py", d, "--request", req2, "--height-at-origin", 1203.0, "--pixel-size", 0.5)
out = os.path.join(d, "t.ifc")
tool("terrain_import.py", os.path.join(d, "terrain", "patch.tif"), os.path.join(d, "terrain", "patch.json"), undeclared, "--request", req2,
     "--out", out, "--profile", PROFILE)
expect("undeclared-ground-level", "B-141", out, PROFILE)
print("test_fixtures: all checks behaved as expected")
