#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test the terrain extension: the error bound of the reduction, the request/patch/import chain, the checker's terrain rules
(each broken in turn), the importer's refusals and the package pin (X-23).

    python3 test_terrain.py [WORK_DIR]

Requires: pip install -r tools/requirements-terrain.txt
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import ifcopenshell

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import terrain_lib as tl  # noqa: E402

_tmp = None if len(sys.argv) > 1 else tempfile.TemporaryDirectory(prefix="terrain-test-")      # removed when the test ends
work = sys.argv[1] if len(sys.argv) > 1 else _tmp.name
os.makedirs(work, exist_ok=True)


def tool(name, *args, expect=0):
    p = subprocess.run([sys.executable, os.path.join(HERE, name), *map(str, args)], capture_output=True, text=True)
    assert p.returncode == expect, "%s exited %d, expected %d: %s" % (name, p.returncode, expect, (p.stderr or p.stdout)[-400:])
    return p


# ------------------------------------------------------------------ 1. the reduction keeps its error bound
rng = np.random.default_rng(7)
y, x = np.mgrid[0:140, 0:140] * 0.234
z = 2.0 * np.sin(x / 6) + 1.5 * np.cos(y / 5) + 0.02 * rng.standard_normal(x.shape) + 0.1 * x
v, t, worst = tl.decimate(z, 0.05)
xy = np.column_stack([v[:, 0] * 0.234, -v[:, 1] * 0.234])
V = np.column_stack([xy, z[v[:, 1], v[:, 0]]])
T = tl.faces_up(xy, t)
pts = np.column_stack([np.tile(np.arange(140), 140) * 0.234, -np.repeat(np.arange(140), 140) * 0.234])
pick = np.random.default_rng(8).choice(len(pts), 400, replace=False)
h = tl.heights_at(V, T, pts[pick])
assert not np.isnan(h).any() and np.abs(h - z.ravel()[pick]).max() <= 0.05 + 1e-9, "the error bound does not hold"
assert len(v) < z.size / 4, "the reduction barely reduced anything"
print("reduction: %d samples -> %d vertices, max error %.4f m (bound 0.05): ok" % (z.size, len(v), worst))

# ------------------------------------------------------------------ 2. request, synthetic ground, import, check
tool("make_sample.py", work)
master = os.path.join(work, "ifc", "example-room-master.ifc")
req = os.path.join(work, "site-request.json")
tool("site_request.py", master, "--floor-elevation", 12.5, "--origin", 100, -40, "--out", req)
PROFILE = os.path.join(work, "terrain-profile.json")
with open(PROFILE, "w") as fh:
    json.dump({"format": "profile/1", "name": "terrain-test", "version": "1.0.0",
               "extensions": {"terrain": {"enabled": True, "crsName": "SYNTHETIC-SITE"}}}, fh)


def make(name, *extra, request=req):
    d = os.path.join(work, name)
    shutil.rmtree(d, ignore_errors=True)
    tool("make_sample_terrain.py", d, "--request", request, *extra)
    out = os.path.join(work, "ifc", name + ".ifc")
    tool("terrain_import.py", os.path.join(d, "terrain", "patch.tif"), os.path.join(d, "terrain", "patch.json"), master,
         "--request", request, "--out", out, "--profile", PROFILE)
    return out


def check(path):
    rep = path + ".report.json"
    p = subprocess.run([sys.executable, os.path.join(HERE, "check_ifc.py"), path, "--profile", PROFILE, "--report", rep],
                       capture_output=True, text=True)
    with open(rep) as fh:
        return p.returncode, json.load(fh)


good = make("slope", "--slope-y", 0.05)
rc, rep = check(good)
assert rc == 0 and rep["result"] == "pass", "a slope with the right floor height must pass: %s" % [f for f in rep["findings"] if f["status"] in ("fail", "warn")]
done = {f["rule"] for f in rep["findings"] if f["status"] == "pass"}
assert {"B-130", "B-131", "B-132", "B-133", "B-134", "B-135", "B-136", "B-137", "B-139", "B-140"} <= done, "terrain rules did not all run: %s" % sorted(done)
print("sample room on a slope: PASS (terrain rules B-130 to B-140 ran)")

# the same file under the default profile: the extension is off, so the terrain is not accepted silently
p = subprocess.run([sys.executable, os.path.join(HERE, "check_ifc.py"), good, "--json"], capture_output=True, text=True)
assert any(f["rule"] == "B-115" and f["status"] == "warn" for f in json.loads(p.stdout)["findings"]), "terrain without the extension not noticed"
print("%-26s expects %-5s -> caught" % ("extension-off", "B-115"))


def expect(name, rule, path):
    rc, rep = check(path)
    hit = [f for f in rep["findings"] if f["rule"] == rule and f["status"] in ("fail", "warn")]
    ok = bool(hit) and (rc == 1 or hit[0]["level"] == "RECOMMENDED")
    print("%-26s expects %-5s -> %s" % (name, rule, "caught" if ok else "NOT CAUGHT"))
    if not ok:
        print(json.dumps(rep["findings"], indent=1))
        sys.exit(1)


expect("floating", "B-136", make("floating", "--height-at-origin", 6.0))            # ground 6.5 m below the floor
expect("buried", "B-136", make("buried", "--height-at-origin", 19.0))               # ground 6.5 m above the floor
expect("seabed", "B-135", make("seabed", "--height-at-origin", -3.0))               # ground below sea level
small = json.load(open(req))
small["patch"]["bounds"] = {"min": [b + 7.0 for b in small["patch"]["bounds"]["min"]], "max": [b - 7.0 for b in small["patch"]["bounds"]["max"]]}
small_req = os.path.join(work, "small-request.json")
json.dump(small, open(small_req, "w"))
expect("patch-too-small", "B-132", make("small", request=small_req))


def mutate(name, rule, fn):
    m = ifcopenshell.open(good)
    fn(m)
    out = os.path.join(work, "ifc", "broken-%s.ifc" % name)
    m.write(out)
    expect(name, rule, out)


def prop(m, name):
    return [p for p in m.by_type("IfcPropertySingleValue") if p.Name == name][0]


def flip(m):
    tfs = m.by_type("IfcTriangulatedFaceSet")[0]
    idx = list(tfs.CoordIndex)
    idx[0] = tuple(reversed(idx[0]))
    tfs.CoordIndex = idx


def rename_crs(m):
    m.by_type("IfcProjectedCRS")[0].Name = "EPSG:4326"


def lose_error_bound(m):
    prop(m, "ErrorBoundMetres").Name = "ErrBound"


def move_site(m):
    m.by_type("IfcSite")[0].RefElevation = 99.0


def blur_frame(m):
    prop(m, "Frame").NominalValue = m.create_entity("IfcText", wrappedValue="somewhere")


def no_site_water(m):
    prop(m, "FootprintInWater").Name = "Wet"


def second_terrain(m):
    t = m.by_type("IfcGeographicElement")[0]
    m.create_entity("IfcGeographicElement", GlobalId=ifcopenshell.guid.new(), Name="Terrain 2", PredefinedType="TERRAIN",
                    Representation=t.Representation, ObjectPlacement=t.ObjectPlacement)


mutate("flipped-triangle", "B-131", flip)
mutate("registry-crs-name", "B-133", rename_crs)
mutate("unpinned-bound", "B-137", lose_error_bound)
mutate("site-elevation", "B-134", move_site)
mutate("frame-unstated", "B-140", blur_frame)
mutate("water-unstated", "B-139", no_site_water)
mutate("two-terrains", "B-130", second_terrain)

# ------------------------------------------------------------------ 3. the importer refuses what it should
d = os.path.join(work, "slope", "terrain")
side = json.load(open(os.path.join(d, "patch.json")))
side["patch"]["sha256"] = "0" * 64
bad_side = os.path.join(work, "bad-sidecar.json")
json.dump(side, open(bad_side, "w"))
tool("terrain_import.py", os.path.join(d, "patch.tif"), bad_side, master, "--request", req, "--out", os.path.join(work, "x.ifc"), expect=3)
other = json.load(open(req))
other["master"]["sha256"] = "1" * 64
bad_req = os.path.join(work, "bad-request.json")
json.dump(other, open(bad_req, "w"))
tool("terrain_import.py", os.path.join(d, "patch.tif"), os.path.join(d, "patch.json"), master, "--request", bad_req, "--out",
     os.path.join(work, "x.ifc"), expect=3)
holes = np.full((20, 20), 5.0)
holes[3, 4] = -9999.0
tl.write_patch(os.path.join(work, "holes.tif"), holes, (0.0, 10.0), 0.5)
try:
    tl.read_patch(os.path.join(work, "holes.tif"))
    sys.exit("a patch with no-data samples was accepted")
except tl.PatchError:
    pass
print("importer refusals (hash, stale request, no-data): ok")

# ------------------------------------------------------------------ 4. the package pins the terrain source (X-23)
pkg = os.path.join(work, "pkg")
shutil.rmtree(pkg, ignore_errors=True)
for sub in ("ifc", "terrain", "reports"):
    os.makedirs(os.path.join(pkg, sub))
shutil.copy(good, os.path.join(pkg, "ifc", "example-room-master.ifc"))
shutil.copy(os.path.join(d, "patch.tif"), os.path.join(pkg, "terrain", "patch.tif"))
shutil.copy(os.path.join(d, "patch.json"), os.path.join(pkg, "terrain", "patch.json"))
shutil.copy(req, os.path.join(pkg, "terrain", "site-request.json"))
shutil.copy(good + ".report.json", os.path.join(pkg, "reports", "check_ifc.json"))
meta = json.load(open(os.path.join(HERE, "..", "templates", "package-meta.template.json")))
meta["delivery"]["id"] = "terrain-test"
meta["provenance"] = [{"asset": "ifc/example-room-master.ifc", "type": "ifc-model", "source": "original", "author": "test", "licence": "CC0-1.0"}] + [
    {"asset": "terrain/" + n, "type": "terrain-patch", "source": "synthetic", "author": "test", "licence": "CC0-1.0"} for n in ("patch.tif", "patch.json")]
meta["licence"]["statement"] = "CC0-1.0"
meta["checks"]["report"] = "reports/check_ifc.json"
meta_path = os.path.join(work, "meta.json")
json.dump(meta, open(meta_path, "w"))


def verify():
    p = subprocess.run([sys.executable, os.path.join(HERE, "build_package.py"), "verify", pkg, "--profile", PROFILE, "--json"], capture_output=True, text=True)
    return [f for f in json.loads(p.stdout)["findings"] if f["rule"] == "X-23"]


tool("build_package.py", "init", pkg, meta_path)
f = verify()
assert f and f[0]["status"] == "fail", "terrain files without a manifest terrain section were accepted"
print("%-26s expects %-5s -> caught" % ("terrain-not-pinned", "X-23"))
real = json.load(open(os.path.join(d, "patch.json")))
meta["terrain"] = {"package": real["package"], "patch": {"path": "terrain/patch.tif", "sha256": real["patch"]["sha256"]},
                   "sidecar": {"path": "terrain/patch.json"}}
json.dump(meta, open(meta_path, "w"))
tool("build_package.py", "init", pkg, meta_path)
f = verify()
assert f and f[0]["status"] == "pass", "a pinned terrain was refused: %s" % f
print("terrain pinned in the manifest: X-23 pass")

# X-23 must also refuse a manifest whose terrain section is malformed or disagrees with the files (never crash)
def broken_pin(label, edit):
    m2 = json.loads(json.dumps(meta))
    edit(m2["terrain"])
    json.dump(m2, open(meta_path, "w"))
    tool("build_package.py", "init", pkg, meta_path)
    p = subprocess.run([sys.executable, os.path.join(HERE, "build_package.py"), "verify", pkg, "--profile", PROFILE, "--json"], capture_output=True, text=True)
    assert p.returncode == 1 and "Traceback" not in p.stderr, "%s: verify exited %d: %s" % (label, p.returncode, p.stderr[-300:])
    got = [f for f in json.loads(p.stdout)["findings"] if f["rule"] == "X-23"]
    assert got and got[0]["status"] == "fail", "%s was accepted: %s" % (label, got)
    print("%-26s expects %-5s -> caught" % (label, "X-23"))


broken_pin("patch-not-an-object", lambda t: t.__setitem__("patch", "terrain/patch.tif"))
broken_pin("sidecar-not-an-object", lambda t: t.__setitem__("sidecar", ["terrain/patch.json"]))
broken_pin("package-missing", lambda t: t.pop("package"))
broken_pin("patch-hash-wrong", lambda t: t["patch"].__setitem__("sha256", "0" * 64))
broken_pin("package-version-wrong", lambda t: t["package"].__setitem__("version", "9.9.9"))
print("test_terrain: all checks behaved as expected")
