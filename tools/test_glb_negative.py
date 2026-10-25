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


# ------------------------------------------------------------------ IFC variant: assemblies with volumes, tilted and inverted placements, terrain
import ifcopenshell  # noqa: E402
import ifcopenshell.guid  # noqa: E402
import uuid  # noqa: E402
import export_glb  # noqa: E402

SAMPLE = os.path.join(ROOT, "deliveries", "example-room")
SRC_IFC = os.path.join(SAMPLE, "ifc", "example-room-master.ifc")
TABLE = "3zDKiH6mrH2Rie17YTXQ7c"
variant_dir = os.path.join(work, "variant")
shutil.rmtree(variant_dir, ignore_errors=True)
os.makedirs(variant_dir)
VARIANT = os.path.join(variant_dir, "variant.ifc")


def make_variant(out):
    m = ifcopenshell.open(SRC_IFC)
    table = m.by_guid(TABLE)
    rel = table.ContainedInStructure[0]
    storey = rel.RelatingStructure

    def local(origin, deg=0.0, axis=(0.0, 0.0, 1.0), ref=None):
        c, s_ = np.cos(np.radians(deg)), np.sin(np.radians(deg))
        ax = m.create_entity("IfcAxis2Placement3D", Location=m.create_entity("IfcCartesianPoint", Coordinates=[float(v) for v in origin]),
                             Axis=m.create_entity("IfcDirection", DirectionRatios=[float(v) for v in axis]),
                             RefDirection=m.create_entity("IfcDirection", DirectionRatios=[float(v) for v in (ref or (c, s_, 0.0))]))
        return m.create_entity("IfcLocalPlacement", PlacementRelTo=storey.ObjectPlacement, RelativePlacement=ax)

    def clone(cls, name, key, origin, deg=0.0, axis=(0.0, 0.0, 1.0), ref=None, **kw):
        return m.create_entity(cls, GlobalId=ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_DNS, key).hex), Name=name,
                               ObjectPlacement=local(origin, deg, axis, ref), Representation=table.Representation, **kw)
    out_ids = {}
    chair = clone("IfcFurnishingElement", "Assembly chair", "neg-chair", (5.0, 5.0, 0.0))
    proxy = clone("IfcBuildingElementProxy", "Assembly clearance", "neg-proxy", (8.0, 8.0, 0.0), PredefinedType="PROVISIONFORSPACE")
    asm = m.create_entity("IfcElementAssembly", GlobalId=ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_DNS, "neg-asm").hex), Name="Chair with clearance",
                          ObjectPlacement=local((5.0, 5.0, 0.0)))
    m.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=asm, RelatedObjects=[chair, proxy])
    lone_proxy = clone("IfcBuildingElementProxy", "Only clearance", "neg-lone", (9.0, 9.0, 0.0), PredefinedType="PROVISIONFORSPACE")
    asm2 = m.create_entity("IfcElementAssembly", GlobalId=ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_DNS, "neg-asm2").hex), Name="Clearance only",
                           ObjectPlacement=local((9.0, 9.0, 0.0)))
    m.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=asm2, RelatedObjects=[lone_proxy])
    tilted = clone("IfcFurnishingElement", "Tilted table", "neg-tilt", (-3.0, 4.0, 0.0), axis=(1.0, 0.0, 1.0), ref=(0.0, 1.0, 0.0))
    inverted = clone("IfcFurnishingElement", "Inverted table", "neg-inv", (-3.0, -4.0, 2.0), axis=(0.0, 0.0, -1.0), ref=(1.0, 0.0, 0.0))
    terrain = clone("IfcGeographicElement", "Test terrain", "neg-terrain", (20.0, 20.0, -1.0), PredefinedType="TERRAIN")
    rel.RelatedElements = list(rel.RelatedElements) + [asm, asm2, tilted, inverted]
    m.write(out)
    out_ids.update(chair=chair.GlobalId, proxy=proxy.GlobalId, asm=asm.GlobalId, lone=lone_proxy.GlobalId, asm2=asm2.GlobalId, tilted=tilted.GlobalId,
                   inverted=inverted.GlobalId, terrain=terrain.GlobalId)
    return out_ids


IDS = make_variant(VARIANT)


def export(path, out, *args):
    shutil.rmtree(out, ignore_errors=True)
    r = py("export_glb.py", path, "--out", out, *args)
    assert r.returncode == 0, r.stdout + r.stderr
    with open(os.path.join(out, "model.glb"), "rb") as fh:
        return fh.read()


def validate_ifc(data, ifc, name="y.glb"):
    d = os.path.join(work, "vg")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    with open(p, "wb") as fh:
        fh.write(data)
    return validate_glb.validate_files([{"path": p, "label": name, "role": "model", "ifc": ifc}], ifc, "off")


def node_box(data, gid):
    doc, bn = glbkit.split_glb(data)
    pts = [it["tri"].reshape(-1, 3) for it in glbkit.triangles_of(doc, bn) if it["extras"].get("globalId") == gid]
    if not pts:
        return None
    a = np.concatenate(pts)
    return a.min(axis=0), a.max(axis=0)


# ------------------------------------------------------------------ 2. --volumes exclude also drops a volume that is part of an assembly
g_mesh = export(VARIANT, os.path.join(work, "o_mesh"))
g_ex = export(VARIANT, os.path.join(work, "o_ex"), "--volumes", "exclude")
lo, hi = node_box(g_mesh, IDS["asm"])
expect(hi[0] > 8.7 and hi[1] > 8.3, "mesh mode: the assembly node holds its clearance proxy (reaches x > 8.7, y > 8.3): %s" % hi.tolist())
lo, hi = node_box(g_ex, IDS["asm"])
expect(hi[0] < 7.0 and hi[1] < 7.0, "exclude mode: the assembly node no longer holds its clearance proxy: %s" % hi.tolist())
doc_ex = glbkit.split_glb(g_ex)[0]
listed = {x["globalId"] for x in doc_ex["extras"]["excluded"]}
expect(IDS["proxy"] in listed and IDS["lone"] in listed, "exclude mode: both proxies are on extras.excluded")
expect(node_box(g_ex, IDS["asm2"]) is None, "exclude mode: an assembly that holds only a volume has no node")
rep = validate_ifc(g_ex, VARIANT)
expect(rep["result"] == "pass" and "GLB-BBOX-IFC" not in codes(rep), "exclude mode: validate_glb --ifc passes: %s %s" % (rep["result"], [m for f in rep["findings"] for m in [f["message"]] if f["status"] != "pass"][:2]))
# a GLB that lists the proxy but still draws it (the defect this test guards) is refused by the IFC comparison
doc_m, bn_m = glbkit.split_glb(g_mesh)
doc_m["extras"]["excluded"] = [dict(x) for x in doc_ex["extras"]["excluded"]]
rep = validate_ifc(repack(doc_m, bn_m), VARIANT)
expect("GLB-BBOX-IFC" in codes(rep), "a model that lists a volume as excluded but still draws it inside an assembly is refused: %s" % codes(rep))
# the exclusion list names only what is really absent: every listed product has no triangle anywhere in the file
doc, bn = glbkit.split_glb(g_ex)
expect(all(node_box(g_ex, gid) is None for gid in listed), "extras.excluded lists only products that have no node")


# ------------------------------------------------------------------ 3. pivot files: explicit errors, nothing ignored
def pivot_run(content, *args, raw=False, name="pf.json", out="o_pf"):
    pf = os.path.join(work, name)
    with open(pf, "w") as fh:
        fh.write(content if raw else json.dumps(content))
    shutil.rmtree(os.path.join(work, out), ignore_errors=True)
    return py("export_glb.py", VARIANT, "--out", os.path.join(work, out), "--pivot-file", pf, *args)


GOOD = IDS["tilted"]
r = pivot_run({GOOD: [1.0, 2.0]}, "--pivots", "placement")
expect(r.returncode == 0, "a good pivot file works: %s" % r.stderr[-200:])
for label, content in {"NaN": '{"%s": [NaN, 2]}' % GOOD, "Infinity": '{"%s": [Infinity, 2]}' % GOOD, "1e400": '{"%s": [1e400, 2]}' % GOOD,
                       "a boolean": '{"%s": [true, 2]}' % GOOD, "a string": '{"%s": ["1", 2]}' % GOOD, "one number": '{"%s": [1]}' % GOOD,
                       "four numbers": '{"%s": [1, 2, 3, 4]}' % GOOD, "a key that is not a GlobalId": '{"hinge": [1, 2]}', "an empty object": "{}", "a list": "[1, 2]",
                       "invalid JSON": "{"}.items():
    r = pivot_run(content, "--pivots", "placement", raw=True)
    expect(r.returncode == 2 and "ERROR" in r.stderr and "Traceback" not in r.stderr and not os.path.exists(os.path.join(work, "o_pf", "model.glb")),
           "pivot file with %s: exit 2, a message, no output: %s" % (label, (r.returncode, r.stderr[-120:])))
r = pivot_run({GOOD: [1.0, 2.0]}, raw=False)
expect(r.returncode == 2 and "--pivots" in r.stderr, "a pivot file with world pivots (the default) is refused, it would do nothing: %s" % r.stderr[-150:])
unknown = "ZZZZZZZZZZZZZZZZZZZZZZ"
r = pivot_run({unknown: [1.0, 2.0]}, "--pivots", "placement")
expect(r.returncode == 3 and unknown in r.stderr and not os.path.exists(os.path.join(work, "o_pf", "model.glb")), "an unknown GlobalId in a pivot file fails and names it: %s" % r.stderr[-200:])
for label, gid in (("terrain", IDS["terrain"]), ("a volume left out", IDS["proxy"]), ("a part of an assembly", IDS["chair"])):
    r = pivot_run({gid: [1.0, 2.0]}, "--pivots", "placement", "--volumes", "exclude")
    expect(r.returncode == 3 and gid in r.stderr, "a pivot file entry for %s is ignored by the exporter, so it fails: %s" % (label, r.stderr[-200:]))
pf_ok = os.path.join(work, "pf-ok.json")
with open(pf_ok, "w") as fh:
    json.dump({GOOD: [1.0, 2.0]}, fh)
g = export(VARIANT, os.path.join(work, "o_pf_ok"), "--pivots", "footprint", "--pivot-file", pf_ok)
expect(glbkit.split_glb(g)[0]["extras"].get("pivotOverrides") == [GOOD], "the applied pivot overrides are recorded in extras.pivotOverrides")
expect("pivotOverrides" not in glbkit.split_glb(export(VARIANT, os.path.join(work, "o_pf_none"), "--pivots", "footprint"))[0]["extras"], "no override, no extras.pivotOverrides")

# ------------------------------------------------------------------ 4. tilted, inverted and terrain placements
g_world = export(VARIANT, os.path.join(work, "o_w"), "--volumes", "exclude")
for mode in ("placement", "footprint"):
    out = os.path.join(work, "o_" + mode)
    g = export(VARIANT, out, "--volumes", "exclude", "--pivots", mode, "--indexed")
    for key in ("tilted", "inverted", "asm", "terrain"):
        a, b = node_box(g, IDS[key]), node_box(g_world, IDS[key])
        expect(a is not None and b is not None and np.allclose(a[0], b[0], atol=1e-4) and np.allclose(a[1], b[1], atol=1e-4), "%s: %s has the same world box as in the baked export" % (mode, key))
    expect(validate_ifc(g, VARIANT)["result"] == "pass", "%s: tilted, inverted, terrain and assembly nodes pass validate_glb --ifc" % mode)
    doc, bn = glbkit.split_glb(g)
    leaf = [n for n in doc["nodes"] if "mesh" in n]
    table = json.load(open(os.path.join(out, "model.placements.json")))
    __import__("jsonschema").validate(table, json.load(open(os.path.join(ROOT, "schemas", "placements.schema.json"))))
    expect(len(table["nodes"]) == len(leaf), "%s: one placements row per leaf node, terrain included (%d rows, %d nodes)" % (mode, len(table["nodes"]), len(leaf)))
    rows = {r["globalId"]: r for r in table["nodes"]}
    t = rows[IDS["terrain"]]
    expect(t["pivot"] == "world" and t["originIfc"] == [0.0, 0.0, 0.0] and t["rotationZDegrees"] == 0.0 and t["placementIfc"] is None, "%s: the terrain row is world, identity: %s" % (mode, t))
    if mode == "placement":
        expect(rows[IDS["tilted"]]["rotationZDegrees"] is None, "placement: a tilted placement has no 'rotation about the vertical' (null): %s" % rows[IDS["tilted"]]["rotationZDegrees"])
        expect(rows[IDS["inverted"]]["rotationZDegrees"] is None, "placement: an inverted placement has no 'rotation about the vertical' (null): %s" % rows[IDS["inverted"]]["rotationZDegrees"])
        expect(rows[IDS["asm"]]["rotationZDegrees"] == 0.0, "placement: an upright placement keeps its yaw")
        node_t = next(n for n in leaf if n["extras"]["globalId"] == IDS["tilted"])
        q = np.array(node_t["rotation"])
        expect(abs(np.linalg.norm(q) - 1) < 1e-6 and abs(q[1]) > 0.1 and abs(q[0]) + abs(q[2]) > 0.1, "placement: the tilted node carries a quaternion that is more than a turn about Y: %s" % q.tolist())
    else:
        expect(rows[IDS["tilted"]]["pivot"] == "footprint" and rows[IDS["tilted"]]["rotationZDegrees"] == 0.0 and rows[IDS["tilted"]]["placementIfc"] is not None,
               "footprint: the row says the node has no rotation and keeps the product's IFC placement for information")
    # shared meshes are named by their shape, not after the first node that uses them
    terrain_mesh = next(n["mesh"] for n in leaf if n["extras"]["globalId"] == IDS["terrain"])
    names = [m.get("name", "") for i, m in enumerate(doc["meshes"]) if i != terrain_mesh]
    expect(names and all(n.startswith("shape:") for n in names), "%s: meshes that nodes share are named by shape: %s" % (mode, names[:3]))
# the default stays as it was: meshes carry the node's name
doc_w = glbkit.split_glb(g_world)[0]
expect(all(not m.get("name", "").startswith("shape:") for m in doc_w["meshes"]), "world pivots: meshes keep the node names (default bytes unchanged)")

# --indexed can be switched off against a profile that turns it on
prof = os.path.join(work, "indexed-profile.json")
with open(prof, "w") as fh:
    json.dump({"name": "indexed-test", "version": "1.0.0", "proofs": {"glbIndexed": True}}, fh)
on = export(VARIANT, os.path.join(work, "o_i_on"), "--profile", prof)
off = export(VARIANT, os.path.join(work, "o_i_off"), "--profile", prof, "--no-indexed")
expect(glbkit.split_glb(on)[0]["extras"].get("indexed") is True and "indexed" not in glbkit.split_glb(off)[0]["extras"] and off == export(VARIANT, os.path.join(work, "o_i_plain")),
       "--no-indexed overrides proofs.glbIndexed")
rpt.load_profile(None)


# the bytes do not depend on the hash seed of the interpreter
seeds = []
for seed in ("0", "7"):
    env = dict(os.environ, PYTHONHASHSEED=seed)
    o = os.path.join(work, "o_seed" + seed)
    shutil.rmtree(o, ignore_errors=True)
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "export_glb.py"), VARIANT, "--out", o, "--pivots", "placement", "--indexed", "--volumes", "exclude"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    seeds.append((open(os.path.join(o, "model.glb"), "rb").read(), open(os.path.join(o, "model.placements.json"), "rb").read()))
expect(seeds[0] == seeds[1], "placement + indexed export is byte-identical under different PYTHONHASHSEED values")


# ------------------------------------------------------------------ 5. coincident faces: edges of the old bucketing, tessellation, union agrees with the finder, budget
def plane_quad(n, p0, x0, y0, x1, y1, up=True):
    """A quad (two triangles) in the plane through p0 with unit normal n, with in-plane corners (x0, y0)..(x1, y1)."""
    n = np.asarray(n, float) / np.linalg.norm(n)
    u, v = coplanar._basis(n)
    c = [np.asarray(p0) + u * x + v * y for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    tri = [c[0], c[1], c[2], c[0], c[2], c[3]]
    return np.array(tri if up else [tri[0], tri[2], tri[1], tri[3], tri[5], tri[4]], float).reshape(-1, 3, 3)


# a normal on the border of a rounding cell (x = 0.1) with noise on either side: the pair must still be found
n1 = np.array([0.1 + 5e-10, 0.0, np.sqrt(1 - (0.1 + 5e-10) ** 2)])
n2 = np.array([0.1 - 5e-10, 0.0, np.sqrt(1 - (0.1 - 5e-10) ** 2)])
tt = np.concatenate([plane_quad(n1, (0, 0, 0), 0, 0, 2, 2), plane_quad(n2, (0, 0, 0), 1, 1, 3, 3)])
rows = coplanar.find_overlaps(tt, np.repeat([0, 1], 2), 0.005)
expect(len(rows) == 1 and abs(rows[0][2] - 1.0) < 1e-6, "two coplanar quads whose normals straddle a rounding border are found: %s" % rows)
for edge in (0.09, 0.095, 0.1, 0.11, 0.5, 0.7071):
    na = np.array([edge + 3e-10, 0.2, 0.0])
    na[2] = np.sqrt(max(0.0, 1 - na[0] ** 2 - na[1] ** 2))
    nb = np.array([edge - 3e-10, 0.2, 0.0])
    nb[2] = np.sqrt(max(0.0, 1 - nb[0] ** 2 - nb[1] ** 2))
    tt = np.concatenate([plane_quad(na, (1, 2, 3), 0, 0, 2, 2), plane_quad(nb, (1, 2, 3), 1, 1, 3, 3)])
    expect(len(coplanar.find_overlaps(tt, np.repeat([0, 1], 2), 0.005)) == 1, "normal x %.4f +- 3e-10: the overlap is found" % edge)
# two planes 3 mm apart, and two planes at 1 degree, are not coincident
tt = np.concatenate([plane_quad((0, 0, 1), (0, 0, 0), 0, 0, 2, 2), plane_quad((0, 0, 1), (0, 0, 0.003), 0, 0, 2, 2)])
expect(coplanar.find_overlaps(tt, np.repeat([0, 1], 2), 0.005) == [], "planes 3 mm apart are not coincident")
tt = np.concatenate([plane_quad((0, 0, 1), (0, 0, 0), 0, 0, 2, 2), plane_quad((np.sin(np.radians(1)), 0, np.cos(np.radians(1))), (0, 0, 0), 0, 0, 2, 2)])
expect(coplanar.find_overlaps(tt, np.repeat([0, 1], 2), 0.005) == [], "planes one degree apart are not coincident")
# fine tessellation is not invisible: 1 cm squares duplicated in a second node
sq = []
for i in range(100):
    for j in range(100):
        sq.append(plane_quad((0, 0, 1), (0, 0, 0), i * 0.01, j * 0.01, (i + 1) * 0.01, (j + 1) * 0.01))
fine = np.concatenate(sq)
rows = coplanar.find_overlaps(np.concatenate([fine, fine]), np.repeat([0, 1], len(fine)), 0.005)
expect(len(rows) == 1 and abs(rows[0][2] - 1.0) < 1e-6, "a 1 m2 patch tessellated into 1 cm squares and duplicated is found: %s" % rows)

# union and finder agree: after the union the finder finds nothing, also at 1 mm and at a cell border
for dz in (0.001, 2e-7, 0.0019):
    z0 = 0.10049999
    a_ = plane_quad((0, 0, 1), (0, 0, z0), 0, 0, 2, 2)
    b_ = plane_quad((0, 0, 1), (0, 0, z0 + dz), 1, 1, 3, 3)
    new, planes, removed = coplanar.union_within({"a": a_, "b": b_})
    both = np.concatenate([new["a"], new["b"]])
    left = coplanar.find_overlaps(both, np.concatenate([np.zeros(len(new["a"]), int), np.ones(len(new["b"]), int)]), 1e-4)
    expect(planes == 1 and abs(removed - 1.0) < 1e-6 and not left, "union at dz=%g leaves nothing for the finder: planes %s, removed %s, left %s" % (dz, planes, removed, left))
# parts of one colour lose no triangle, and the colours decide a shared area in a fixed order
red, blue = (0.9, 0.1, 0.1, 1.0), (0.1, 0.1, 0.9, 1.0)
q1 = plane_quad((0, 0, 1), (0, 0, 0), 0, 0, 1, 1).reshape(-1, 3)
q2 = plane_quad((0, 0, 1), (0, 0, 0), 5, 5, 6, 6).reshape(-1, 3)
same_colour, planes, _ = coplanar.union_parts([(red, q1), (red, q2)])
expect(len(same_colour) == 1 and len(same_colour[0][1]) == 12, "two parts of one colour keep all their triangles: %s" % [len(p[1]) // 3 for p in same_colour])
big = plane_quad((0, 0, 1), (0, 0, 0), 0, 0, 2, 2).reshape(-1, 3)
sm = plane_quad((0, 0, 1), (0, 0, 0), 1, 1, 3, 3).reshape(-1, 3)
for order in ([(red, big), (blue, sm)], [(blue, sm), (red, big)]):
    out, planes, removed = coplanar.union_parts(order)
    areas = {p[0]: float(np.linalg.norm(np.cross(p[1].reshape(-1, 3, 3)[:, 1] - p[1].reshape(-1, 3, 3)[:, 0], p[1].reshape(-1, 3, 3)[:, 2] - p[1].reshape(-1, 3, 3)[:, 0]), axis=1).sum() / 2) for p in out}
    expect(abs(areas[blue] - 4.0) < 1e-6 and abs(areas[red] - 3.0) < 1e-6, "the lowest (r, g, b, a) keeps the shared area whatever the input order: %s" % areas)

# the budget: an error that says so, never a clean result
tt = np.concatenate([plane_quad((0, 0, 1), (0, 0, 0), 0, 0, 2, 2), plane_quad((0, 0, 1), (0, 0, 0), 1, 1, 3, 3)])
try:
    coplanar.find_overlaps(tt, np.repeat([0, 1], 2), 0.005, max_triangles=3)
    expect(False, "a triangle budget that is too small must raise")
except glbkit.Failed as exc:
    expect("budget" in str(exc), "the triangle budget raises Failed: %s" % exc)
try:
    coplanar.find_overlaps(tt, np.repeat([0, 1], 2), 0.005, seconds=-1)
    expect(False, "a time budget that is used up must raise")
except glbkit.Failed as exc:
    expect("time" in str(exc), "the time budget raises Failed: %s" % exc)
dup = os.path.join(work, "dup.glb")
with open(dup, "wb") as fh:
    fh.write(scene([comp("A", "structure", "AAAAAAAAAAAAAAAAAAAAAA", (0, 0, 0, 2, 2, 1)), comp("B", "structure", "BBBBBBBBBBBBBBBBBBBBBB", (0, 0, 0, 2, 2, 1))]))
r = py("coplanar.py", dup, "--max-triangles", "5")
expect(r.returncode == 3 and "budget" in r.stderr and "Traceback" not in r.stderr, "coplanar.py: an exhausted budget is exit 3 with a message: %s %s" % (r.returncode, r.stderr[-150:]))
r = py("coplanar.py", dup)
expect(r.returncode == 0 and "pair(s)" in r.stdout, "coplanar.py finds the duplicated boxes: %s" % r.stdout[:150])
expect(py("coplanar.py", dup, "--min-area", "-1").returncode == 2, "coplanar.py: a negative --min-area is a command-line error")


# ------------------------------------------------------------------ 6. walk check: stairs, tall buildings, size budget, bad options, malformed input
import walkcheck  # noqa: E402


def stair_house(riser, n=8, tread=0.28, width=(1.0, 2.2)):
    """A ground slab, a flight of n solid steps and an upper slab that the last step is part of; two rooms (ground before the stair, upper after it)."""
    comps = [comp("Ground slab", "structure", "G1", (0, 0, -0.2, 6, 3, 0))]
    x_top = 1.0 + (n - 1) * tread
    for k in range(1, n + 1):
        comps.append(comp("Step %d" % k, "structure", "S%d" % k, (1.0 + (k - 1) * tread, width[0], 0, 1.0 + k * tread, width[1], k * riser)))
    h = n * riser
    comps.append(comp("Upper slab", "structure", "U1", (x_top, 0, h - 0.2, 7, 3, h)))
    rooms = [{"id": "ground", "name": "G", "function": "x", "level": "Ground", "external": False, "min": [0, 0, 0], "max": [1, 3, 2.6], "footprint": [[0, 0], [0.9, 0], [0.9, 3], [0, 3]]},
             {"id": "upper", "name": "U", "function": "x", "level": "Upper", "external": False, "min": [x_top + 0.4, 0, h], "max": [7, 3, h + 2.6],
              "footprint": [[x_top + 0.4, 0.3], [6.8, 0.3], [6.8, 2.7], [x_top + 0.4, 2.7]]}]
    return scene(comps, rooms=rooms, levels=[{"name": "Ground", "elevation": 0.0}, {"name": "Upper", "elevation": h}])


def upper_reachable(rep, rad):
    e = rep["radii"][walkcheck.radius_key(rad)]
    return e["startFound"] and next(r for r in e["rooms"] if r["id"] == "upper")["reachable"]


for riser in (0.15, 0.16, 0.175, 0.18, 0.19):
    g = stair_house(riser)
    rep = walkcheck.walk(g, (0.5, 1.5, 0.0), [0.15, 0.20, 0.30])
    expect(all(upper_reachable(rep, r) for r in (0.15, 0.20, 0.30)), "stairs with a riser of %.3f m and a tread of 0.28 m are climbed by default bodies of radius 0.15, 0.20 and 0.30" % riser)
# a riser above the stated limit cuts the stair off, and --step / --riser change that
g = stair_house(0.25)
expect(not upper_reachable(walkcheck.walk(g, (0.5, 1.5, 0.0), [0.15]), 0.15), "a riser of 0.25 m is above the default step height: the upper room is cut off")
expect(upper_reachable(walkcheck.walk(g, (0.5, 1.5, 0.0), [0.15], step=0.25), 0.15), "... and reachable with --step 0.25")
with open(os.path.join(work, "stair.glb"), "wb") as fh:
    fh.write(stair_house(0.175))
sg = os.path.join(work, "stair.glb")
r = py("walkcheck.py", sg, "--start", "0.5,1.5,0", "--radius", "0.30", "--require", "0.30", "--riser", "0.30")
expect(r.returncode == 0, "--riser 0.30 is a documented option and the stair is still climbed: %s" % (r.stdout + r.stderr)[-200:])
r = py("walkcheck.py", sg, "--start", "0.5,1.5,0", "--riser", "0.1")
expect(r.returncode == 2 and "--riser" in r.stderr, "--riser below --step is a command-line error: %s" % r.stderr[-120:])
profile_step = os.path.join(work, "stair-profile.json")
with open(profile_step, "w") as fh:
    json.dump({"name": "stairs", "version": "1.0.0", "geometry": {"stairRiserLimitMetres": 0.25}}, fh)
with open(os.path.join(work, "stair25.glb"), "wb") as fh:
    fh.write(stair_house(0.25))
r = py("walkcheck.py", os.path.join(work, "stair25.glb"), "--start", "0.5,1.5,0", "--radius", "0.15", "--require", "0.15", "--profile", profile_step)
expect(r.returncode == 0, "the default step height comes from the profile (geometry.stairRiserLimitMetres 0.25): %s" % (r.stdout + r.stderr)[-200:])
r = py("walkcheck.py", os.path.join(work, "stair25.glb"), "--start", "0.5,1.5,0", "--radius", "0.15", "--require", "0.15")
expect(r.returncode == 1, "... and without it the 0.25 m stair is cut off (exit 1): %s" % r.returncode)

# levels more than 12 m above the lowest point are inside the grid
tall = scene([comp("Slab 0", "structure", "A0", (0, 0, -0.2, 10, 6, 0)), comp("Slab 6", "structure", "A6", (0, 0, 5.8, 10, 6, 6)), comp("Slab 15", "structure", "A15", (0, 0, 14.8, 10, 6, 15))],
             rooms=[{"id": "r%d" % h, "name": "R", "function": "x", "level": "L%d" % h, "external": False, "min": [0, 0, h], "max": [10, 6, h + 2.6], "footprint": [[0, 0], [10, 0], [10, 6], [0, 6]]} for h in (0, 6, 15)],
             levels=[{"name": "L%d" % h, "elevation": float(h)} for h in (0, 6, 15)])
rep = walkcheck.walk(tall, (5.0, 3.0, 0.0), [0.30], res=0.1)
rooms = {r["id"]: r for r in rep["radii"]["0.30"]["rooms"]}
expect(rooms["r15"]["walkableAreaM2"] > 50 and not rooms["r15"]["reachable"] and rooms["r0"]["reachable"], "a room 15 m up is in the grid (walkable area %s) and cut off because it is: %s" % (rooms["r15"]["walkableAreaM2"], rooms["r15"]))
expect(rep["grid"]["cells"][2] >= 150, "the grid is as tall as the model: %s" % rep["grid"]["cells"])

# size budget: stated, checked before allocating, a clear error
huge = scene([comp("Huge", "structure", "H1", (0, 0, -0.2, 3000, 3000, 0))])
for kw, needle in (({}, "million cells"), ({"max_mb": 10 ** 9}, "samples")):
    try:
        walkcheck.walk(huge, (1.0, 1.0, 0.0), [0.30], **kw)
        expect(False, "a huge model must be refused (%s)" % needle)
    except glbkit.Failed as exc:
        expect(needle in str(exc) and "--res" in str(exc), "a huge model is refused with a suggestion (%s): %s" % (needle, str(exc)[:160]))
hp = os.path.join(work, "huge.glb")
with open(hp, "wb") as fh:
    fh.write(huge)
r = py("walkcheck.py", hp, "--start", "1,1,0")
expect(r.returncode == 3 and "Traceback" not in r.stderr and "--res" in r.stderr, "walkcheck.py: the size budget is exit 3 with a message: %s" % r.stderr[-200:])
r = py("walkcheck.py", sg, "--start", "0.5,1.5,0", "--max-memory-mb", "1")
expect(r.returncode == 3 and "--max-memory-mb" in r.stderr, "--max-memory-mb sets the budget: %s" % r.stderr[-150:])
# one big triangle is cut into pieces and sampled in batches, and covers its surface
big_tri = np.array([[[0, 0, 0], [40, 0, 0], [0, 30, 0]]], float)
batches = list(walkcheck.sample_triangles(big_tri, 0.0225))
npts = sum(len(b[0]) for b in batches)
expect(max(len(b[0]) for b in batches) <= 2_100_000, "sampling is done in batches of about 2 million points at most: %s" % [len(b[0]) for b in batches][:5])
expect(npts >= 0.9 * walkcheck.sample_count(big_tri, 0.0225) * 0.5 and all((b[0][:, 0] / 40 + b[0][:, 1] / 30 <= 1 + 1e-9).all() and (b[0] >= -1e-9).all() for b in batches), "all samples of a big triangle lie on it")
cover = np.zeros((int(40 / 0.1) + 1, int(30 / 0.1) + 1), bool)
for pts, _ in batches:
    cover[np.floor(pts[:, 0] / 0.1).astype(int), np.floor(pts[:, 1] / 0.1).astype(int)] = True
inside = np.array([[(i + 0.5) * 0.1 / 40 + (j + 0.5) * 0.1 / 30 < 0.99 for j in range(cover.shape[1])] for i in range(cover.shape[0])])
expect(cover[inside].all(), "... and leave no 10 cm cell of the triangle uncovered")

# bad numbers are command-line errors, not silent changes of the answer
for args in (["--radius", "-0.3"], ["--radius", "nan"], ["--radius", "0"], ["--res", "0"], ["--res", "nan"], ["--step", "-1"], ["--step", "nan"], ["--body-height", "0"], ["--require", "0"],
             ["--require", "-1"], ["--require", "nan"], ["--max-memory-mb", "0"], ["--riser", "nan"]):
    r = py("walkcheck.py", sg, "--start", "0.5,1.5,0", *args)
    expect(r.returncode == 2 and "Traceback" not in r.stderr and "ERROR" in r.stderr, "walkcheck.py %s: exit 2 with a message: %s %s" % (" ".join(args), r.returncode, r.stderr[-100:]))
for start in ("nan,1,0", "inf,1,0", "1,2"):
    r = py("walkcheck.py", sg, "--start=" + start)
    expect(r.returncode == 2 and "Traceback" not in r.stderr, "--start=%s: exit 2: %s" % (start, r.stderr[-100:]))
r = py("walkcheck.py", sg, "--start", "0.5,1.5,0", "--waypoint", "w=1,nan,0")
expect(r.returncode == 2, "a waypoint with NaN is a command-line error")
# radii that differ by less than a key's two decimals keep their own entries
rep = walkcheck.walk(stair_house(0.15), (0.5, 1.5, 0.0), [0.301, 0.304, 0.30])
expect(sorted(rep["radii"]) == ["0.30", "0.301", "0.304"], "radii 0.30, 0.301 and 0.304 have three keys: %s" % sorted(rep["radii"]))
# --require 0.30 is honoured and a start that is not on a standing place is not a success
r = py("walkcheck.py", sg, "--start=-1,1,0")
expect(r.returncode == 1 and "not on a standing place" in (r.stdout + r.stderr), "a start that is not on a standing place exits 1: %s" % r.returncode)
r = py("walkcheck.py", sg, "--start", "0.5,1.5,0", "--radius", "0.30", "--require", "0.30")
expect(r.returncode == 0, "(control) the stair house passes --require 0.30")
r = py("walkcheck.py", sg, "--start", "0.5,1.5,0", "--radius", "3.0", "--require", "3.0")
expect(r.returncode == 1, "a radius of 3 m fits nowhere: --require exits 1 (%d)" % r.returncode)

# malformed input is exit 3 with a message, never a traceback
def broken(mutate, name):
    doc, bn = glbkit.split_glb(stair_house(0.175))
    mutate(doc)
    path = os.path.join(work, name)
    with open(path, "wb") as fh:
        fh.write(repack(doc, bn))
    return py("walkcheck.py", path, "--start", "0.5,1.5,0")


cases = {"a room without a footprint": lambda d: d["extras"]["rooms"][0].pop("footprint"),
         "a room with a footprint of strings": lambda d: d["extras"]["rooms"][0].__setitem__("footprint", [["a", "b"]] * 3),
         "a level without a name": lambda d: d["extras"]["levels"][0].pop("name"),
         "rooms that is not a list": lambda d: d["extras"].__setitem__("rooms", 5),
         "an index out of range": lambda d: d["nodes"][2].__setitem__("mesh", 99)}
for label, mut in cases.items():
    r = broken(mut, "broken.glb")
    expect(r.returncode == 3 and "Traceback" not in r.stderr and "ERROR" in r.stderr, "walkcheck.py with %s: exit 3 with a message: %s %s" % (label, r.returncode, r.stderr[-120:]))
# bounds in extras that are smaller than the geometry no longer cut it
small = broken(lambda d: d["extras"].__setitem__("bounds", {"min": [0, 0, 0], "max": [1, 1, 1]}), "small-bounds.glb")
expect(small.returncode == 0 and "upper" in small.stdout, "extras.bounds smaller than the geometry are not trusted: %s" % (small.stdout + small.stderr)[-200:])
nan_b = broken(lambda d: d["extras"].__setitem__("bounds", {"min": [float("nan")] * 3, "max": [1, 1, 1]}), "nan-bounds.glb")
expect(nan_b.returncode == 0 and "upper" in nan_b.stdout, "NaN extras.bounds are not used, the grid comes from the triangles: %s" % (nan_b.stdout + nan_b.stderr)[-200:])
# scipy missing: a clear message
import builtins  # noqa: E402
real_import = builtins.__import__


def no_scipy(name, *a, **k):
    if name == "scipy" or name.startswith("scipy."):
        raise ImportError("no scipy")
    return real_import(name, *a, **k)


builtins.__import__ = no_scipy
try:
    try:
        walkcheck.walk(stair_house(0.175), (0.5, 1.5, 0.0), [0.30])
        expect(False, "walk without scipy must fail")
    except glbkit.Failed as exc:
        expect("scipy" in str(exc) and "requirements" in str(exc), "a missing scipy is named with the fix: %s" % exc)
finally:
    builtins.__import__ = real_import


# ------------------------------------------------------------------ 7. a staged copy of the set: empty, truncated, tampered, escaping or stale manifests
import check_set  # noqa: E402
import hashlib  # noqa: E402
import zipfile  # noqa: E402


def staged(name):
    """A fresh copy of the set (without deliveries, dist and caches) whose version is a release and whose manifests are regenerated for the copy."""
    cp = os.path.join(work, name)
    shutil.rmtree(cp, ignore_errors=True)
    shutil.copytree(ROOT, cp, ignore=shutil.ignore_patterns("deliveries", "work", "__pycache__", ".git", "node_modules", "dist", ".*"))
    ver = json.load(open(os.path.join(ROOT, "rules.json")))["version"]
    with open(os.path.join(cp, "CHANGELOG.md"), encoding="utf-8") as fh:
        text = fh.read()
    import re as _re
    text = _re.sub(r"^## Unreleased[^\n]*", "## " + ver, text, count=1, flags=_re.M)
    with open(os.path.join(cp, "CHANGELOG.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    r = subprocess.run([sys.executable, "-I", os.path.join(cp, "tools", "gen_all.py"), "--write"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return cp, ver


def cs(cp, *args):
    r = py("check_set.py", cp, "--json", *args)
    try:
        return r.returncode, json.loads(r.stdout), r.stderr
    except ValueError:
        return r.returncode, {"problems": [r.stdout + r.stderr]}, r.stderr


def make_dist(cp, ver):
    """A small dist/ for the copy: two documents, a zip of the whole set and the checksum files, the way build_dist.py writes them."""
    d = os.path.join(cp, "dist")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    name = "builders-guide-" + ver
    for ext, body in (("html", b"<html>guide</html>"), ("pdf", b"%PDF-1.4 guide")):
        with open(os.path.join(d, "%s.%s" % (name, ext)), "wb") as fh:
            fh.write(body)
    sys.path.insert(0, cp + "/tools")
    import fileset as fs  # the copy's own list
    sys.path.pop(0)
    with open(os.path.join(cp, "MANIFEST.sha256"), "w", newline="\n") as fh:
        fh.write(fs.checksum_text(cp))
    zp = os.path.join(d, name + ".zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in fs.set_files(cp) + fs.dist_files(cp) + ["MANIFEST.sha256"]:
            z.writestr(name + "/" + rel, open(os.path.join(cp, rel), "rb").read())
    zh = hashlib.sha256(open(zp, "rb").read()).hexdigest()
    open(zp + ".sha256", "w").write("%s  %s\n" % (zh, os.path.basename(zp)))
    with open(os.path.join(d, "SHA256SUMS.txt"), "w") as fh:
        for fn in (name + ".zip", name + ".html", name + ".pdf"):
            fh.write("%s  %s\n" % (hashlib.sha256(open(os.path.join(d, fn), "rb").read()).hexdigest(), fn))
    return name


cp, VER = staged("staged-a")
code, rj, err = cs(cp, "--expect", VER)
expect(code == 0 and rj["listed"] > 300 and rj["extra"] == [], "a clean staged copy passes and has no extra files: %s %s" % (code, rj["problems"] or rj.get("extra")))
shutil.copy(os.path.join(cp, "MANIFEST.sha256"), os.path.join(work, "MANIFEST.sha256.good"))
good_manifest = open(os.path.join(work, "MANIFEST.sha256.good")).read()


def put_manifest(text):
    with open(os.path.join(cp, "MANIFEST.sha256"), "w", newline="\n") as fh:
        fh.write(text)


put_manifest("")
code, rj, _ = cs(cp)
expect(code == 1 and any("lists no files" in x for x in rj["problems"]), "an empty MANIFEST.sha256 fails: %s %s" % (code, rj["problems"][:2]))
put_manifest("\n".join(("%s *%s" % tuple(ln.split("  ", 1))) for ln in good_manifest.splitlines()) + "\n")
code, rj, _ = cs(cp)
expect(code == 1 and any("line 1 is not" in x for x in rj["problems"]), "a binary-mode (hash *path) manifest fails with its line number: %s" % rj["problems"][:2])
put_manifest("".join(good_manifest.splitlines(True)[:5]))
code, rj, _ = cs(cp)
expect(code == 1 and any("MANIFEST.json lists" in x for x in rj["problems"]), "a manifest truncated to 5 rows fails (MANIFEST.json lists more): %s" % rj["problems"][:2])
put_manifest(good_manifest.rstrip("\n"))
code, rj, _ = cs(cp)
expect(code == 1 and any("newline" in x for x in rj["problems"]), "a manifest without its final newline fails: %s" % rj["problems"][:2])
put_manifest(good_manifest + "0" * 64 + "  /etc/hostname\n" + "0" * 64 + "  ../../outside.txt\n")
code, rj, _ = cs(cp)
expect(code == 1 and sum("is not a path inside the set" in x for x in rj["problems"]) == 2, "absolute and .. paths in the manifest are refused: %s" % rj["problems"][:3])
# a file removed with its row from MANIFEST.sha256 only, or from both lists
put_manifest("".join(ln for ln in good_manifest.splitlines(True) if not ln.rstrip().endswith("  tools/render.py")))
os.remove(os.path.join(cp, "tools", "render.py"))
code, rj, _ = cs(cp)
expect(code == 1 and any("MANIFEST.json lists" in x for x in rj["problems"]), "a tool deleted together with its MANIFEST.sha256 row is still found through MANIFEST.json: %s" % rj["problems"][:2])
shutil.copy(os.path.join(ROOT, "tools", "render.py"), os.path.join(cp, "tools", "render.py"))
put_manifest(good_manifest)
# a program added to tools/
with open(os.path.join(cp, "tools", "evil.py"), "w") as fh:
    fh.write("print(1)\n")
code, rj, _ = cs(cp)
expect(code == 0 and rj["extra"] == ["tools/evil.py"], "an unlisted program is named in `extra` and passes without --strict: %s" % rj["extra"])
r = py("check_set.py", cp)
expect("tools/evil.py" in r.stdout, "... and is named in the text output: %s" % r.stdout[-200:])
code, rj, _ = cs(cp, "--strict")
expect(code == 1 and any(x.startswith("extra:") for x in rj["problems"]), "... and fails with --strict")
os.remove(os.path.join(cp, "tools", "evil.py"))
# a symbolic link as a listed file, a dangling tool link, a non-UTF-8 CHANGELOG
os.remove(os.path.join(cp, "AGENTS.md"))
os.symlink("/etc/hostname", os.path.join(cp, "AGENTS.md"))
code, rj, err = cs(cp)
expect(code == 1 and any("symbolic links" in x for x in rj["problems"]) and "Traceback" not in err, "a listed file that is a symbolic link is refused: %s" % rj["problems"][:2])
os.remove(os.path.join(cp, "AGENTS.md"))
shutil.copy(os.path.join(ROOT, "AGENTS.md"), os.path.join(cp, "AGENTS.md"))
os.symlink("/nonexistent/target.py", os.path.join(cp, "tools", "dangling.py"))
code, rj, err = cs(cp)
expect(code in (0, 1) and "Traceback" not in err and rj.get("result") in ("pass", "fail"), "a dangling symbolic link in tools/ is not a traceback: %s %s" % (code, err[-150:]))
os.remove(os.path.join(cp, "tools", "dangling.py"))
cl = os.path.join(cp, "CHANGELOG.md")
orig_cl = open(cl, "rb").read()
with open(cl, "ab") as fh:
    fh.write(b"\xff\xfe")
code, rj, err = cs(cp)
expect(code == 1 and "Traceback" not in err and rj.get("problems"), "a CHANGELOG that is not UTF-8 is a failed check with JSON, not a traceback: %s %s" % (code, err[-150:]))
open(cl, "wb").write(orig_cl)
# a tree under development
open(cl, "wb").write(orig_cl.replace(b"## " + VER.encode(), b"## Unreleased (proposed)", 1))
code, rj, _ = cs(cp)
expect(code == 1 and any("not a release" in x for x in rj["problems"]), "a CHANGELOG headed Unreleased is not a release: %s" % rj["problems"][:2])
code, rj, _ = cs(cp, "--allow-unreleased")
expect(code == 1, "(--allow-unreleased accepts the heading, but the changed CHANGELOG no longer matches its manifest row) %s" % rj["problems"][:1])
open(cl, "wb").write(orig_cl)
code, rj, _ = cs(cp, "--expect", VER)
expect(code == 0, "(control) the copy is clean again: %s" % rj["problems"][:2])

# dist/: stale version, tampered zip, tampered document, wrong checksum file
name = make_dist(cp, VER)
code, rj, _ = cs(cp, "--expect", VER)
expect(code == 0 and rj["dist"]["zip"] == name + ".zip", "a copy with a complete dist/ passes: %s" % rj["problems"][:3])
zp = os.path.join(cp, "dist", name + ".zip")
orig_zip = open(zp, "rb").read()
with zipfile.ZipFile(zp, "w") as z:
    for rel in check_set.fileset.set_files(cp) + check_set.fileset.dist_files(cp) + ["MANIFEST.sha256"]:
        data = open(os.path.join(cp, rel), "rb").read()
        if rel == "tools/export_glb.py":
            data += b"# tampered\n"
        if rel != "tools/walkcheck.py":
            z.writestr(name + "/" + rel, data)
    z.writestr(name + "/tools/extra.py", b"x = 1\n")
code, rj, _ = cs(cp)
text = " ".join(rj["problems"])
expect(code == 1 and "lacks 1" in text and "holds 1 file(s) that are not in the manifest" in text and "differ from the manifest, for example tools/export_glb.py" in text and "SHA256SUMS.txt says" in text,
       "a zip with a changed, a missing and an extra member is refused: %s" % rj["problems"])
open(zp, "wb").write(orig_zip)
html = os.path.join(cp, "dist", name + ".html")
open(html, "ab").write(b" ")
code, rj, _ = cs(cp)
expect(code == 1 and any("dist/" + name + ".html" in x for x in rj["problems"]), "a changed dist document is refused: %s" % rj["problems"][:2])
open(html, "wb").write(b"<html>guide</html>")
os.rename(html, os.path.join(cp, "dist", "builders-guide-1.0.0.html"))
code, rj, _ = cs(cp)
expect(code == 1 and any("1.0.0" in x and "stale" in x for x in rj["problems"]), "a dist document of another version is refused as stale: %s" % rj["problems"][:3])
os.rename(os.path.join(cp, "dist", "builders-guide-1.0.0.html"), html)
shutil.rmtree(os.path.join(cp, "dist"))
code, rj, _ = cs(cp, "--expect", VER)
expect(code == 0 and rj["dist"] is None, "a staged copy without dist/ is fine (the documents are exempt from 'missing')")
expect(py("check_set.py", os.path.join(work, "variant")).returncode == 3 and py("check_set.py", cp, "--expect", "x").returncode == 2, "exit codes 3 (not a set) and 2 (usage)")


if __name__ == "__main__":
    print("test_glb_negative: %s" % ("all checks behaved as expected" if not FAILS else "%d failure(s)" % len(FAILS)))
    sys.exit(1 if FAILS else 0)
