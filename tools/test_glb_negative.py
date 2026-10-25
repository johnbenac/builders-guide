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


if __name__ == "__main__":
    print("test_glb_negative: %s" % ("all checks behaved as expected" if not FAILS else "%d failure(s)" % len(FAILS)))
    sys.exit(1 if FAILS else 0)
