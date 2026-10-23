#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Counterexamples and bad inputs for the automated checks and the terrain tools: models that must stay clean (a skylight, thick
walls, a raised threshold, an open edge), models that must be caught (a partial roof, a floor finish posing as a ceiling, a proxy
below the floor, a flight under another), terrain inputs that must be refused, adversarial surfaces for the error bound, and the
promise that the same script writes the same bytes in another process.

    python3 test_hardening.py [WORK_DIR]

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
import ifc_author  # noqa: E402
import terrain_lib as tl  # noqa: E402

_tmp = None
if len(sys.argv) > 1:
    work = sys.argv[1]
    os.makedirs(work, exist_ok=True)
else:
    _tmp = tempfile.TemporaryDirectory(prefix="hardening-test-")
    work = _tmp.name


def run(script, *args, env=None):
    return subprocess.run([sys.executable, os.path.join(HERE, script), *map(str, args)], capture_output=True, text=True, env=env)


def tool(script, *args, expect=0):
    p = run(script, *args)
    assert p.returncode == expect, "%s exited %d, expected %d: %s" % (script, p.returncode, expect, (p.stderr or p.stdout)[-400:])
    return p


def findings(path, rule, profile=None):
    rep = path + ".report.json"
    cmd = ["check_ifc.py", path, "--report", rep] + (["--profile", profile] if profile else [])
    run(*cmd)
    with open(rep) as fh:
        return [f for f in json.load(fh)["findings"] if f["rule"] == rule]


def status(path, rule, profile=None):
    f = findings(path, rule, profile)
    return {x["status"] for x in f}


def want(name, path, rule, expect_status, absent=(), profile=None):
    got = status(path, rule, profile)
    ok = (expect_status in got) and not (set(absent) & got)
    print("%-34s %-5s expects %-4s -> %s" % (name, rule, expect_status, "ok" if ok else "WRONG (got %s)" % sorted(got)))
    assert ok, "%s: %s expected %s, got %s" % (name, rule, expect_status, sorted(got))


# ------------------------------------------------------------------ small buildings
H = 3.0


def styles(b):
    return {k: b.style(k, c, o) for k, c, o in (("tray", "#d9cdb0", 1.0), ("wall", "#a98d63", 1.0), ("room", "#f4f1ea", 1.0), ("door", "#8fb8b8", 0.45),
                                                ("glass", "#91c8d0", 0.45), ("stair", "#b9a584", 1.0), ("cover", "#8c6f4e", 1.0))}


def one_room(name, w=6.0, d=5.0, roof="full", floor_finish_only=False):
    b = ifc_author.Builder("hardening/" + name, name, "Site", name, "B-" + name.upper())
    L = b.level("Building - ground / +0 m", 0.0)
    b.at(L)
    c = styles(b)
    ops = (c["room"], c["door"], c["glass"])
    b.slab("floor", "Floor", [b.box(-0.3, -0.3, -0.3, w + 0.6, d + 0.6, 0.3, c["tray"])])
    for k, r in {"s": (-0.3, -0.3, w + 0.3, 0), "n": (-0.3, d, w + 0.3, d + 0.3), "w": (-0.3, 0, 0, d), "e": (w, 0, w + 0.3, d)}.items():
        b.wall(k, "Wall " + k, r, H, c["wall"], [], opening_styles=ops)
    if floor_finish_only:
        b.add("IfcCovering", "finish", "Floor finish", [b.box(0, 0, 0, w, d, 0.12, c["cover"])], PredefinedType="FLOORING")
    elif roof == "full":
        b.slab("roof", "Roof", [b.box(-0.3, -0.3, H, w + 0.6, d + 0.6, 0.3, c["tray"])], kind="ROOF")
    elif roof == "skylight":
        slab = b.slab("roof", "Roof", [b.box(-0.3, -0.3, H, w + 0.6, d + 0.6, 0.3, c["tray"])], kind="ROOF")
        b.opening("sky", slab, w / 2 - 1.0, d / 2 - 1.0, H - 0.02, 2.0, 2.0, 0.34, c["room"])
    elif roof == "partial":
        b.slab("roof", "Roof", [b.box(w / 2 - 2.0, -0.3, H, 4.0, d + 0.6, 0.3, c["tray"])], kind="ROOF")
    b.room("R-1", "Room", "work room", [(0, 0), (w, 0), (w, d), (0, d)], "floor", c["room"], height=H)
    return b, c


def build(b, name):
    return b.write(work, name + ".ifc")


# B-54: a roof with a skylight is a roof; a roof over a fifth of the room and a floor finish are not
for name, kw, expect_status in (("roof-full", dict(roof="full"), "pass"), ("roof-skylight", dict(roof="skylight"), "pass"),
                                ("roof-partial", dict(w=20.0, roof="partial"), "warn"), ("floor-finish-only", dict(floor_finish_only=True), "warn")):
    b, _ = one_room(name, **kw)
    want(name, build(b, name), "B-54", expect_status, absent=("warn",) if expect_status == "pass" else ())

# B-47: a door joins a hall to a cell however thick the wall or high the threshold; without a way through the cell is lost; touching
# rooms with no wall are joined by an open edge
def two_rooms(name, t=0.3, sill=0.0, door=True, open_edge=False, arch=False, arch_sill=0.0):
    b = ifc_author.Builder("hardening/" + name, name, "Site", name, "B-" + name.upper())
    L = b.level("Building - ground / +0 m", 0.0)
    b.at(L)
    c = styles(b)
    ops = (c["room"], c["door"], c["glass"])
    gap = 0.0 if open_edge else t
    b.slab("floor", "Floor", [b.box(-0.3, -0.3, -0.3, 8.6 + gap, 4.6, 0.3, c["tray"])])
    b.slab("roof", "Roof", [b.box(-0.3, -0.3, H + 0.65, 8.6 + gap, 4.6, 0.3, c["tray"])], kind="ROOF")
    if not open_edge:
        w = b.wall("p", "Partition", (4.0, 0.0, 4.0 + t, 4.0), H + 0.6, c["wall"], [("door", 1.0, 1.0, sill, sill + 2.1)] if door and not arch else [],
                   along="y", opening_styles=ops)
        if arch:               # a through-opening with nothing in it
            b.opening("arch", w, 4.0 - 0.02, 1.0, arch_sill, t + 0.04, 1.0, 2.1, c["room"])
    b.room("T-HALL", "Hall", "hall", [(0, 0), (4, 0), (4, 4), (0, 4)], "f", c["room"], circulation=True, height=H + 0.6)
    b.room("T-CELL", "Cell", "cell", [(4 + gap, 0), (8 + gap, 0), (8 + gap, 4), (4 + gap, 4)], "f", c["room"], height=H + 0.6)
    return b


for name, kw, expect_status in (("wall-thin", dict(), "pass"), ("wall-1200", dict(t=1.2), "pass"), ("raised-threshold", dict(sill=0.6), "pass"),
                                ("open-edge", dict(open_edge=True), "pass"), ("no-way-through", dict(door=False), "warn"),
                                ("archway", dict(arch=True), "pass"), ("archway-thick-wall", dict(arch=True, t=1.2), "pass"),
                                ("opening-too-high-to-walk", dict(arch=True, arch_sill=1.5), "warn")):
    want(name, build(two_rooms(name, **kw), name), "B-47", expect_status, absent=("warn",) if expect_status == "pass" else ())

# B-142: a proxy is not exempt, a reservation volume and a footing are
for name, mk, expect_status in (("proxy-below-floor", lambda b, c: b.add("IfcBuildingElementProxy", "p", "Dump", [b.box(1, 1, -3.0, 1, 1, 0.5, c["wall"])], PredefinedType="USERDEFINED"), "warn"),
                                ("reservation-below-floor", lambda b, c: b.add("IfcBuildingElementProxy", "p", "Reserved", [b.box(1, 1, -3.0, 1, 1, 0.5, c["wall"])], PredefinedType="PROVISIONFORSPACE"), "pass"),
                                ("footing-below-floor", lambda b, c: b.footing("f", "Footing", [b.box(1, 1, -3.0, 1, 1, 0.5, c["wall"])]), "pass")):
    b, c = one_room(name)
    mk(b, c)
    want(name, build(b, name), "B-142", expect_status, absent=("warn",) if expect_status == "pass" else ())

# B-61: a flight over another takes its head-room; a clean flight gets a pass message
b = ifc_author.Builder("hardening/stairs", "stairs", "Site", "stairs", "B-STAIRS")
L = b.level("Building - ground / +0 m", 0.0)
b.at(L)
c = styles(b)
b.slab("floor", "Floor", [b.box(-1, -1, -0.3, 10, 6, 0.3, c["tray"])])
b.stair("b", "Flight B", (1.0, 3.0), (1, 0), 1.0, 1.0, 3.0, c["stair"])
p = build(b, "stair-clean")
want("single-flight", p, "B-61", "pass", absent=("warn",))
b.stair("a", "Flight A", (1.0, 3.0), (1, 0), 1.0, 0.0, 3.0, c["stair"])
p = build(b, "stair-stacked")
f = findings(p, "B-61")
assert any(x["status"] == "warn" and "Flight A" in x["message"] for x in f), "a flight under another flight must lose head-room: %s" % f
print("%-34s B-61  expects warn naming Flight A -> ok" % "flight-under-flight")

# the kit refuses what it should
for label, fn in (("unknown opening kind", lambda b, c: b.wall("w", "W", (0, 0, 5, 0.3), H, c["wall"], [("dor", 1, 1, 0, 2.1)], opening_styles=(c["room"],) * 3)),
                  ("opening outside the wall", lambda b, c: b.wall("w", "W", (0, 0, 5, 0.3), H, c["wall"], [("door", 4.8, 1, 0, 2.1)], opening_styles=(c["room"],) * 3)),
                  ("overlapping openings", lambda b, c: b.wall("w", "W", (0, 0, 5, 0.3), H, c["wall"], [("door", 1, 1, 0, 2.1), ("window", 1.5, 1, 0.9, 2.0)], opening_styles=(c["room"],) * 3)),
                  ("repeated key", lambda b, c: (b.slab("k", "A", []), b.slab("k", "B", []))),
                  ("style with two colours", lambda b, c: (b.style("a", "#ff0000"), b.style("a", "#00ff00"))),
                  ("zero rise", lambda b, c: b.stair_plan(0.0))):
    b2 = ifc_author.Builder("hardening/kit", "k", "S", "k", "B-K")
    b2.level("L", 0.0)
    b2.at(0)
    try:
        fn(b2, styles(b2))
    except ValueError:
        continue
    sys.exit("the kit accepted: " + label)
try:
    ifc_author.Builder("hardening/kit", "k", "S", "k", "B-K").at(0)
    sys.exit("the kit accepted use before the first level")
except ValueError:
    pass
assert ifc_author.Builder("x", "k", "S", "k", "B-K").stair_well((0, 0), (1, 0), 1.0, 0.0, 3.0, 9.0) is None, "no cut is needed under a high ceiling"
hdr = ifc_author.Builder("x", "k", "S", "k", "B-K")
hdr.level("L", 0.0)
out = hdr.write(work, "hdr.ifc", author="O'Brien \\1 ·", organisation="Org")
text = open(out, "rb").read().decode("ascii")
assert "('O''Brien \\\\1 \\X2\\00B7\\X0\\')" in text, "the header author is not written as an escaped STEP string"
ifcopenshell.open(out)
print("authoring kit refusals and header escaping: ok")

# ------------------------------------------------------------------ terrain: bad inputs are refused, awkward ones are handled
tool("make_sample.py", work)
master = os.path.join(work, "ifc", "example-room-master.ifc")
req = os.path.join(work, "req.json")
PROFILE = os.path.join(work, "terrain-profile.json")
with open(PROFILE, "w") as fh:
    json.dump({"format": "profile/1", "name": "t", "version": "1", "extensions": {"terrain": {"enabled": True, "crsName": "SYNTHETIC-SITE"}}}, fh)
tool("site_request.py", master, "--floor-elevation", 12.5, "--origin", 100, -40, "--out", req)
tool("make_sample_terrain.py", work, "--request", req, "--slope-y", 0.05)
good_side = json.load(open(os.path.join(work, "terrain", "patch.json")))
good_z, good_info = tl.read_patch(os.path.join(work, "terrain", "patch.tif"))
origin = (good_side["patch"]["origin"]["x"], good_side["patch"]["origin"]["y"])


def raw_tif(path, z, scale=(0.5, 0.5, 0.0), tie=True, scale_tag=True, geokey=1, transformation=False, nodata_tag=None):
    from PIL import Image, TiffImagePlugin
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    if scale_tag:
        ifd[tl.TAG_PIXEL_SCALE] = scale
        ifd.tagtype[tl.TAG_PIXEL_SCALE] = 12
    if tie:
        ifd[tl.TAG_TIEPOINT] = (0.0, 0.0, 0.0, origin[0], origin[1], 0.0)
        ifd.tagtype[tl.TAG_TIEPOINT] = 12
    if geokey is not None:
        ifd[tl.TAG_GEOKEYS] = (1, 1, 0, 1, tl.KEY_RASTER_TYPE, 0, 1, geokey)
        ifd.tagtype[tl.TAG_GEOKEYS] = 3
    if transformation:
        ifd[tl.TAG_TRANSFORMATION] = tuple([0.5, 0, 0, origin[0], 0, -0.5, 0, origin[1], 0, 0, 0, 0, 0, 0, 0, 1])
        ifd.tagtype[tl.TAG_TRANSFORMATION] = 12
    if nodata_tag is not None:
        ifd[tl.TAG_NODATA] = nodata_tag
    Image.fromarray(np.asarray(z, dtype=np.float32), mode="F").save(path, tiffinfo=ifd, compression="tiff_adobe_deflate")


def importer(tag, tif, side=None, extra=(), request=req, profile=PROFILE, out=None, expect=3):
    d = os.path.join(work, "case-" + tag)
    os.makedirs(d, exist_ok=True)
    s = json.loads(json.dumps(good_side if side is None else side))
    s["patch"]["file"] = "patch.tif"
    s["patch"]["sha256"] = tl.sha256_file(tif)
    shutil.copy(tif, os.path.join(d, "patch.tif"))
    with open(os.path.join(d, "patch.json"), "w") as fh:
        json.dump(s, fh)
    p = run("terrain_import.py", os.path.join(d, "patch.tif"), os.path.join(d, "patch.json"), master, "--request", request, "--out",
            out or os.path.join(d, "out.ifc"), "--profile", profile, *extra)
    ok = p.returncode == expect
    print("%-34s importer exit %d expects %d -> %s" % (tag, p.returncode, expect, "ok" if ok else "WRONG: " + (p.stderr or p.stdout)[-200:]))
    assert ok
    return os.path.join(d, "out.ifc")


h, w = good_z.shape
raw_tif(os.path.join(work, "ok.tif"), good_z)
importer("control-ok", os.path.join(work, "ok.tif"), expect=0)
raw_tif(os.path.join(work, "nonsquare.tif"), good_z, scale=(0.5, 2.0, 0.0))
importer("non-square-pixels", os.path.join(work, "nonsquare.tif"))
raw_tif(os.path.join(work, "notags.tif"), good_z, tie=False, scale_tag=False, geokey=None)
importer("no-geotags", os.path.join(work, "notags.tif"))
raw_tif(os.path.join(work, "point.tif"), good_z, geokey=2)
importer("pixel-is-point", os.path.join(work, "point.tif"))
raw_tif(os.path.join(work, "xform.tif"), good_z, transformation=True)
importer("model-transformation", os.path.join(work, "xform.tif"))
pit = good_z.copy()
pit[10:25, 10:25] = -9999.0
raw_tif(os.path.join(work, "pit.tif"), pit)
importer("sentinel-without-tag", os.path.join(work, "pit.tif"))
raw_tif(os.path.join(work, "badtag.tif"), good_z, nodata_tag="not-a-number")
importer("unparsable-nodata-tag", os.path.join(work, "badtag.tif"))
huge = good_z.copy()
huge[3, 3] = 1e30
raw_tif(os.path.join(work, "huge.tif"), huge)
importer("implausible-height", os.path.join(work, "huge.tif"))
importer("negative-error-bound", os.path.join(work, "ok.tif"), extra=("--error-bound", -1))
importer("zero-error-bound", os.path.join(work, "ok.tif"), extra=("--error-bound", 0))
importer("output-is-the-master", os.path.join(work, "ok.tif"), out=master)
small_cap = os.path.join(work, "cap-profile.json")
json.dump({"format": "profile/1", "name": "t", "version": "1", "extensions": {"terrain": {"enabled": True, "crsName": "SYNTHETIC-SITE", "maxPatchSamples": 100}}}, open(small_cap, "w"))
importer("too-many-samples", os.path.join(work, "ok.tif"), profile=small_cap)
shifted = json.loads(json.dumps(good_side))
shifted["patch"]["origin"]["x"] += 30.0
raw_tif(os.path.join(work, "ok2.tif"), good_z)
importer("sidecar-origin-disagrees", os.path.join(work, "ok.tif"), side=shifted)
req_wide = json.load(open(req))
req_wide["patch"]["bounds"]["max"][0] += 30.0
wide = os.path.join(work, "req-wide.json")
json.dump(req_wide, open(wide, "w"))
importer("patch-does-not-cover-request", os.path.join(work, "ok.tif"), request=wide)
other_frame = json.loads(json.dumps(good_side))
other_frame["frame"] = "somewhere else"
importer("sidecar-frame-differs", os.path.join(work, "ok.tif"), side=other_frame)

# a rough patch: the reduction stops at the triangle cap, and a file it does write passes its own checker
rng = np.random.default_rng(3)
rough = 12.5 + 0.5 * rng.standard_normal(good_z.shape)
raw_tif(os.path.join(work, "rough.tif"), rough)
cap_tri = os.path.join(work, "cap-tri-profile.json")
json.dump({"format": "profile/1", "name": "t", "version": "1", "extensions": {"terrain": {"enabled": True, "crsName": "SYNTHETIC-SITE", "maxTriangles": 200}}}, open(cap_tri, "w"))
importer("rough-patch-over-triangle-cap", os.path.join(work, "rough.tif"), profile=cap_tri)
out = importer("rough-patch-site-elevation", os.path.join(work, "rough.tif"), expect=0)
want("rough-patch passes its own B-134", out, "B-134", "pass", absent=("fail",), profile=PROFILE)
want("terrain within its triangle cap", out, "B-138", "pass", absent=("warn", "fail"), profile=PROFILE)
want("water declared on the site", out, "B-139", "pass", absent=("warn", "fail"), profile=PROFILE)

# B-131 cannot be fooled by an overlap and a hole of equal area
good_ifc = os.path.join(work, "case-control-ok", "out.ifc")
m = ifcopenshell.open(good_ifc)
tfs = m.by_type("IfcTriangulatedFaceSet")[0]
pts = np.array(tfs.Coordinates.CoordList)
corner = lambda fx, fy: int(np.argmin(np.abs(pts[:, 0] - (pts[:, 0].min() if fx == 0 else pts[:, 0].max())) + np.abs(pts[:, 1] - (pts[:, 1].min() if fy == 0 else pts[:, 1].max())))) + 1
A, B, C, D = corner(0, 0), corner(1, 0), corner(1, 1), corner(0, 1)
tfs.CoordIndex = [(A, B, C), (A, B, D)]            # both face up, the areas add up, they overlap near AB and leave the corner B C D bare
bad = os.path.join(work, "overlap-and-hole.ifc")
m.write(bad)
f = findings(bad, "B-131", PROFILE)
assert any(x["status"] == "fail" and "same direction" in x["message"] for x in f), f
print("%-34s B-131 expects fail -> ok" % "overlap-and-hole-of-equal-area")
want("terrain over its triangle cap", out, "B-138", "warn", profile=cap_tri)

# ------------------------------------------------------------------ adversarial surfaces: the error bound holds at every sample
from scipy.interpolate import LinearNDInterpolator  # noqa: E402


def bound_holds(name, z, eps=0.05):
    v, t, worst = tl.decimate(z, eps, max_rounds=500)
    zi = LinearNDInterpolator(v.astype(float), z[v[:, 1], v[:, 0]])
    rr, cc = np.mgrid[0:z.shape[0], 0:z.shape[1]]
    zh = zi(cc.ravel().astype(float), rr.ravel().astype(float))
    err = np.nanmax(np.abs(zh - z.ravel()))
    assert not np.isnan(zh).any() and err <= eps + 1e-9, "%s: error %.4f over the bound" % (name, err)
    print("%-34s %6d samples -> %5d vertices, max error %.4f ok" % (name, z.size, len(v), err))


yy, xx = np.mgrid[0:60, 0:60].astype(float)
bound_holds("checkerboard", 5.0 * (((xx // 3) + (yy // 3)) % 2))
spike = np.zeros((60, 60))
spike[30, 30] = 40.0
bound_holds("spike", spike)
bound_holds("step", np.where(xx > 29, 8.0, 0.0))
bound_holds("ridge", 6.0 * np.exp(-((xx - 30) / 2.0) ** 2))
bound_holds("thin 3 by 200", np.random.default_rng(5).standard_normal((3, 200)))
bound_holds("thin 200 by 2", np.random.default_rng(6).standard_normal((200, 2)))
bound_holds("noise", np.random.default_rng(7).standard_normal((60, 60)))

# ------------------------------------------------------------------ the same script writes the same bytes in another process
outs = []
for seed in ("1", "2"):
    d = os.path.join(work, "det" + seed)
    env = dict(os.environ, PYTHONHASHSEED=seed)
    p = subprocess.run([sys.executable, os.path.join(HERE, "make_fixtures.py"), d], capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr[-300:]
    outs.append(d)
for n in ("tray-house", "hillside-block", "courtyard"):
    a = open(os.path.join(outs[0], n, "ifc", "master.ifc"), "rb").read()
    b_ = open(os.path.join(outs[1], n, "ifc", "master.ifc"), "rb").read()
    assert a == b_, "%s differs between processes" % n
print("fixtures are byte-identical across processes with different hash seeds")
print("test_hardening: all checks behaved as expected")
