#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests of the optional GLB export and check features: reservation-volume exclusion with its report, per-element pivots with instancing and a
placements table, node-transform-aware bounds and identity checks, coplanar-face detection and union, the walk check at a body radius, and the
packet-staging check.

    python3 tools/test_glb_options.py [WORK_DIR]

Starts from the sample delivery `deliveries/example-room/` (read only), makes a variant of its master IFC file with a zone, a reservation
volume, a second table turned about the vertical axis, and a fixed coplanar overlap, and checks the behaviour of the tools on it. Requires
tools/requirements.txt.
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
work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="glb-options-test-")
os.makedirs(work, exist_ok=True)
FAILS = []


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FAIL", msg)


def py(script, *args):
    return subprocess.run([sys.executable, "-I", os.path.join(HERE, script), *map(str, args)], capture_output=True, text=True)


import numpy as np  # noqa: E402
import ifcopenshell  # noqa: E402
import ifcopenshell.guid  # noqa: E402
import export_glb  # noqa: E402
import glbkit  # noqa: E402
import report as rpt  # noqa: E402
import validate_glb  # noqa: E402

rpt.load_profile(None)
SAMPLE = os.path.join(ROOT, "deliveries", "example-room")
SRC_IFC = os.path.join(SAMPLE, "ifc", "example-room-master.ifc")
TABLE = "3zDKiH6mrH2Rie17YTXQ7c"


# ------------------------------------------------------------------ a variant of the sample master
def make_variant(out):
    """The sample master plus: a zone and a PROVISIONFORSPACE proxy (both with a box), a second copy of the table turned 30 degrees about Z and
    placed elsewhere (same shape as the first: one mesh when instanced), and a floor-finish slab exactly on top of the floor slab (coplanar)."""
    m = ifcopenshell.open(SRC_IFC)
    table = m.by_guid(TABLE)
    rel = table.ContainedInStructure[0]
    storey = rel.RelatingStructure

    def local(origin, deg):
        c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
        ax = m.create_entity("IfcAxis2Placement3D", Location=m.create_entity("IfcCartesianPoint", Coordinates=[float(v) for v in origin]),
                             Axis=m.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, 1.0]),
                             RefDirection=m.create_entity("IfcDirection", DirectionRatios=[float(c), float(s), 0.0]))
        return m.create_entity("IfcLocalPlacement", PlacementRelTo=storey.ObjectPlacement, RelativePlacement=ax)

    def clone(cls, name, key, origin, deg, **kw):
        e = m.create_entity(cls, GlobalId=ifcopenshell.guid.compress(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_DNS, key).hex), Name=name,
                            ObjectPlacement=local(origin, deg), Representation=table.Representation, **kw)
        return e
    table2 = clone("IfcFurnishingElement", "Second table", "glb-options-table2", (1.0, 1.0, 0.0), 30.0)
    zone = clone("IfcSpatialZone", "Dolly zone", "glb-options-zone", (2.0, 1.5, 0.0), 0.0)
    proxy = clone("IfcBuildingElementProxy", "Reserved clear volume", "glb-options-proxy", (0.5, 2.5, 0.0), 0.0, PredefinedType="PROVISIONFORSPACE")
    rel.RelatedElements = list(rel.RelatedElements) + [table2, proxy]
    m.write(out)
    return {"table2": table2.GlobalId, "zone": zone.GlobalId, "proxy": proxy.GlobalId}


variant_dir = os.path.join(work, "variant")
shutil.rmtree(variant_dir, ignore_errors=True)
os.makedirs(variant_dir)
VARIANT = os.path.join(variant_dir, "variant.ifc")
IDS = make_variant(VARIANT)


def export(path, out, *args):
    shutil.rmtree(out, ignore_errors=True)
    r = py("export_glb.py", path, "--out", out, *args)
    assert r.returncode == 0, r.stdout + r.stderr
    return open(os.path.join(out, "model.glb"), "rb").read()


def validate(data, ifc=None, name="x.glb"):
    d = os.path.join(work, "vg")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name)
    open(p, "wb").write(data)
    return validate_glb.validate_files([{"path": p, "label": name, "role": "model", "ifc": ifc}], ifc, "off")


def codes(rep):
    return sorted({f.get("code") or f["rule"] for f in rep["findings"] if f["status"] in ("fail", "warn")})


def nodes_of(data):
    doc, bn = glbkit.split_glb(data)
    return doc, bn, [n for n in doc["nodes"] if "mesh" in n]


# ------------------------------------------------------------------ 1. volumes: mesh by default, exclude on request, written down
g_mesh = export(VARIANT, os.path.join(work, "o_mesh"))
doc, _, leaf = nodes_of(g_mesh)
gids = {n["extras"]["globalId"] for n in leaf}
expect(IDS["zone"] in gids and IDS["proxy"] in gids, "default (mesh): zone and reservation volume are exported like any product")
expect("excluded" not in doc["extras"], "default (mesh): no exclusion report")
expect(validate(g_mesh, VARIANT)["result"] == "pass", "default (mesh): the model passes the IFC comparison: %s" % codes(validate(g_mesh, VARIANT)))

g_ex = export(VARIANT, os.path.join(work, "o_ex"), "--volumes", "exclude")
doc, _, leaf = nodes_of(g_ex)
gids = {n["extras"]["globalId"] for n in leaf}
expect(IDS["zone"] not in gids and IDS["proxy"] not in gids and IDS["table2"] in gids, "exclude: the two volumes have no node, the table still has")
ex = doc["extras"]["excluded"]
expect(sorted(x["globalId"] for x in ex) == sorted([IDS["zone"], IDS["proxy"]]) and {x["reason"] for x in ex} == {"zone", "reservation"},
       "exclude: the report names both volumes with their reason: %s" % ex)
rep = validate(g_ex, VARIANT)
expect(rep["result"] == "pass" and rep["files"][0].get("ifcExcluded") == 2, "exclude: validate_glb --ifc accepts the report: %s %s" % (codes(rep), rep["files"][0]))
expect(g_ex == export(VARIANT, os.path.join(work, "o_ex2"), "--volumes", "exclude"), "exclude: the export is deterministic")
# the same GLB against an IFC file that has a node missing for a real product is still refused
# (1) the report hides a wall
doc, bn = glbkit.split_glb(g_ex)
wall = next(n for n in doc["nodes"] if n.get("name", "").startswith("structure:South wall"))
wid = wall["extras"]["globalId"]


def repack(doc, bn):
    js = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("ascii")
    js += b" " * (-len(js) % 4)
    bn = bytes(bn) + b"\0" * (-len(bn) % 4)
    return b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bn), b"BIN\0") + bn


d2 = json.loads(json.dumps(doc))
d2["extras"]["excluded"].append({"globalId": wid, "ifcClass": "IfcWall", "name": "South wall", "predefinedType": "", "reason": "zone"})
rep = validate(repack(d2, bn), VARIANT)
expect("GLB-BBOX-IFC" in codes(rep), "a wall on the exclusion list is refused (and a listed product with a node)")
# (2) a volume left out without being listed
d3 = json.loads(json.dumps(doc))
d3["extras"]["excluded"] = [x for x in d3["extras"]["excluded"] if x["reason"] != "zone"]
rep = validate(repack(d3, bn), VARIANT)
expect("GLB-BBOX-IFC" in codes(rep), "a volume without a node that is not on the list is refused")
# (3) a malformed report
d4 = json.loads(json.dumps(doc))
d4["extras"]["excluded"] = [{"globalId": 5}]
expect("GLB-EXTRAS" in codes(validate(repack(d4, bn), VARIANT)), "a malformed exclusion report is named GLB-EXTRAS")
# the mode can come from the profile
prof = os.path.join(work, "volumes-profile.json")
json.dump({"name": "volumes-test", "version": "1.0.0", "proofs": {"glbVolumes": "exclude"}}, open(prof, "w"))
g_prof = export(VARIANT, os.path.join(work, "o_prof"), "--profile", prof)
expect(g_prof == g_ex, "profile proofs.glbVolumes=exclude gives the same bytes as --volumes exclude")
rpt.load_profile(None)

# ------------------------------------------------------------------ 3. bounds and identity respect node transforms
def pivoted(data, name_start, delta_gltf, translation_error=(0.0, 0.0, 0.0)):
    """The same scene with one node's vertices moved by -delta (so the node has a real origin) and the node translated by +delta (+ an error)."""
    doc, bn = glbkit.split_glb(data)
    bn = bytearray(bn)
    node = next(n for n in doc["nodes"] if n.get("name", "").startswith(name_start))
    for pr in doc["meshes"][node["mesh"]]["primitives"]:
        acc = doc["accessors"][pr["attributes"]["POSITION"]]
        bv = doc["bufferViews"][acc["bufferView"]]
        arr = np.frombuffer(bn, dtype="<f4", count=acc["count"] * 3, offset=bv["byteOffset"]).reshape(-1, 3)
        arr -= np.array(delta_gltf, dtype="<f4")
        acc["min"], acc["max"] = [float(x) for x in arr.min(axis=0)], [float(x) for x in arr.max(axis=0)]
    node["translation"] = [float(d + e) for d, e in zip(delta_gltf, translation_error)]
    return doc, bn


base = g_ex
doc0, _ = glbkit.split_glb(base)
tname = next(n["name"] for n in doc0["nodes"] if n.get("name", "").startswith("furniture:Work table"))
d, b = pivoted(base, tname, (2.0, 0.0, -1.5))
good_pivot = repack(d, b)
rep = validate(good_pivot, VARIANT)
expect(rep["result"] == "pass" and not codes(rep), "a node with a pivot (moved vertices + translation) passes the bounds and IFC comparison: %s" % codes(rep))
expect(rep["files"][0]["boundsIfcFrame"] == validate(base, VARIANT)["files"][0]["boundsIfcFrame"], "the reported bounds are those of the scene, not of the mesh arrays")
d, b = pivoted(base, tname, (2.0, 0.0, -1.5), (0.5, 0.0, 0.0))
rep = validate(repack(d, b), VARIANT)
expect("GLB-BBOX-IFC" in codes(rep), "a node whose transform puts it 0.5 m from its IFC box is caught: %s" % codes(rep))
d, b = pivoted(base, tname, (2.0, 0.0, -1.5), (9000.0, 0.0, 0.0))
rep = validate(repack(d, b), VARIANT)
expect({"GLB-BOUNDS", "GLB-EXTENT"} <= set(codes(rep)), "extent and extras.bounds are those of the transformed scene: %s" % codes(rep))
d, b = pivoted(base, tname, (2.0, 0.0, -1.5))
nd = next(n for n in d["nodes"] if n.get("name") == tname)
nd["extras"]["globalId"] = "0000000000000000000000"
rep = validate(repack(d, b))
expect("GLB-IDENT" in codes(rep) and rep["result"] == "pass", "a node whose extras.globalId differs from its name is a RECOMMENDED finding: %s" % codes(rep))
nd["extras"]["globalId"] = tname.rsplit("#", 1)[1]
other = next(n for n in d["nodes"] if n.get("name", "").startswith("furniture:Second table"))
other["extras"]["globalId"] = nd["extras"]["globalId"]
other["name"] = "furniture:Second table#" + nd["extras"]["globalId"]
rep = validate(repack(d, b))
expect("GLB-IDENT" in codes(rep), "one GlobalId on two nodes is named: %s" % codes(rep))
# a rotation that is not in the IFC file moves the box
d, b = pivoted(base, tname, (0.0, 0.0, 0.0))
nd = next(n for n in d["nodes"] if n.get("name") == tname)
nd["rotation"] = [0.0, 0.7071068, 0.0, 0.7071068]
rep = validate(repack(d, b), VARIANT)
expect("GLB-BOUNDS" in codes(rep) or "GLB-BBOX-IFC" in codes(rep), "a rotation that is not in the IFC file is caught by the bounds comparison: %s" % codes(rep))

# ------------------------------------------------------------------ 2. pivots, instancing, indexed meshes, placements table
def per_product_boxes(data):
    doc, bn = glbkit.split_glb(data)
    out = {}
    for it in glbkit.triangles_of(doc, bn):
        t = it["tri"].reshape(-1, 3)
        gid = it["extras"]["globalId"]
        lo, hi = t.min(axis=0), t.max(axis=0)
        out[gid] = (lo, hi) if gid not in out else (np.minimum(out[gid][0], lo), np.maximum(out[gid][1], hi))
    return out


def triangle_count(data):
    doc, bn = glbkit.split_glb(data)
    return sum(len(i["tri"]) for i in glbkit.triangles_of(doc, bn))


world = g_ex
boxes_world = per_product_boxes(world)
for mode in ("placement", "footprint"):
    out = os.path.join(work, "o_" + mode)
    g = export(VARIANT, out, "--volumes", "exclude", "--pivots", mode)
    rep = validate(g, VARIANT)
    expect(rep["result"] == "pass" and not codes(rep), "%s: the pivoted model passes validate_glb --ifc: %s" % (mode, codes(rep)))
    boxes = per_product_boxes(g)
    expect(boxes.keys() == boxes_world.keys() and all(np.allclose(boxes[k][0], boxes_world[k][0], atol=1e-4) and np.allclose(boxes[k][1], boxes_world[k][1], atol=1e-4) for k in boxes),
           "%s: every product has the same world box as in the baked export" % mode)
    expect(triangle_count(g) == triangle_count(world), "%s: the same number of triangles" % mode)
    expect(g == export(VARIANT, os.path.join(work, "o_%s2" % mode), "--volumes", "exclude", "--pivots", mode), "%s: the export is deterministic" % mode)
    doc, _, leaf = nodes_of(g)
    expect(doc["extras"]["nodePivots"] == mode, "%s: extras.nodePivots names the mode" % mode)
    table = json.load(open(os.path.join(out, "model.placements.json")))
    expect(table["format"] == "placements/1" and len(table["nodes"]) == len(leaf) and table["modelSha256"] == glbkit.sha256_bytes(g),
           "%s: the placements table lists every node and the hash of the model" % mode)
    names = {r["node"] for r in table["nodes"]}
    expect(all(r["instanceOf"] in names | {None} for r in table["nodes"]), "%s: instanceOf names a node of the table" % mode)
    if mode == "placement":
        t1 = next(n for n in leaf if n["name"].startswith("furniture:Work table"))
        t2 = next(n for n in leaf if n["name"].startswith("furniture:Second table"))
        expect(t1["mesh"] == t2["mesh"], "placement: the two tables (same shape, one turned) share one mesh")
        r2 = next(n for n in table["nodes"] if n["node"] == t2["name"])
        expect("rotation" in t2 and abs(r2["rotationZDegrees"] - 30.0) < 1e-3 and np.allclose(r2["originIfc"][:2], [1.0, 1.0], atol=1e-6),
               "placement: the second table is a translation and a 30 degree turn about the vertical: %s" % r2)
        expect(np.allclose(t2["translation"], [1.0, 0.0, -1.0], atol=1e-6), "placement: translation is the placement in glTF axes: %s" % t2["translation"])
        expect(len({n["mesh"] for n in leaf}) < len(leaf), "placement: fewer meshes than nodes")
        q = np.array(t2["rotation"])
        expect(abs(np.linalg.norm(q) - 1) < 1e-6 and abs(q[1] - np.sin(np.radians(15))) < 1e-6 and abs(q[0]) < 1e-9 and abs(q[2]) < 1e-9, "placement: the rotation is about glTF Y by 30 degrees: %s" % q.tolist())
        pivot_ok = [n for n in leaf if n.get("translation") or n.get("rotation")]
        expect(len(pivot_ok) >= 1, "placement: nodes carry transforms")
    else:
        expect(all("translation" in n and "rotation" not in n for n in leaf if n["extras"]["kind"] in ("furniture", "window", "door")), "footprint: translation only")
        # the footprint pivot is the centre of the footprint at the lowest point
        r = next(r for r in table["nodes"] if r["node"].startswith("furniture:Work table"))
        lo, hi = boxes_world[r["globalId"]]
        expect(np.allclose(r["originIfc"], [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]], atol=1e-5), "footprint: origin of the Work table is its footprint centre at the lowest point")
# a pivot file puts the origin of one product on a given point (a hinge) and keeps its world geometry
pf = os.path.join(work, "pivots.json")
json.dump({IDS["table2"]: [2.0, 1.25]}, open(pf, "w"))
out = os.path.join(work, "o_override")
g = export(VARIANT, out, "--volumes", "exclude", "--pivots", "placement", "--pivot-file", pf)
doc, _, leaf = nodes_of(g)
t2 = next(n for n in leaf if n["extras"]["globalId"] == IDS["table2"])
lo2 = boxes_world[IDS["table2"]][0]
expect(np.allclose(t2["translation"], [2.0, lo2[2], -1.25], atol=1e-6) and "rotation" not in t2, "pivot file: origin at the given point, z at the lowest point: %s" % t2)
expect(validate(g, VARIANT)["result"] == "pass" and all(np.allclose(per_product_boxes(g)[k][0], boxes_world[k][0], atol=1e-4) for k in boxes_world), "pivot file: world geometry unchanged")
bad_pf = os.path.join(work, "bad-pivots.json")
json.dump([1, 2], open(bad_pf, "w"))
expect(py("export_glb.py", VARIANT, "--out", os.path.join(work, "o_badpf"), "--pivot-file", bad_pf).returncode == 2, "a malformed pivot file is a command-line error (exit 2)")
# a mirrored placement cannot be a node transform: it falls back to the footprint pivot
parts = [((0.5, 0.5, 0.5, 1.0), np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float))]
mir = np.diag([-1.0, 1.0, 1.0, 1.0])
world_parts = [(c, t @ mir[:3, :3].T) for c, t in parts]
_, node, _, _, kind = export_glb.pivot_node(mir, parts, world_parts, "placement", None)
expect(kind == "footprint" and node["rotation"] is None, "a mirrored placement falls back to the footprint pivot")
# quaternions agree with the reader's matrices
rng_ = np.random.default_rng(3)
for _ in range(20):
    qq = rng_.normal(size=4)
    qq /= np.linalg.norm(qq)
    m4 = glbkit.node_matrix({"rotation": [float(v) for v in qq]})
    q2 = glbkit.quaternion_of(m4[:3, :3])
    expect(np.allclose(glbkit.node_matrix({"rotation": q2})[:3, :3], m4[:3, :3], atol=1e-7), "quaternion_of inverts node_matrix")
# indexed meshes
gi = export(VARIANT, os.path.join(work, "o_idx"), "--volumes", "exclude", "--indexed")
doc, _, leaf = nodes_of(gi)
expect(all("indices" in pr for n in leaf for pr in doc["meshes"][n["mesh"]]["primitives"]) and len(gi) < len(world), "indexed: every primitive has indices and the file is smaller (%d < %d)" % (len(gi), len(world)))
expect(validate(gi, VARIANT)["result"] == "pass" and triangle_count(gi) == triangle_count(world), "indexed: passes and keeps the triangles")
both = export(VARIANT, os.path.join(work, "o_both"), "--volumes", "exclude", "--indexed", "--pivots", "placement")
expect(validate(both, VARIANT)["result"] == "pass" and len(both) < len(gi), "indexed + placement: passes and is smaller again (%d < %d)" % (len(both), len(gi)))
# the defaults did not change: the delivered proofs of the sample are what a default export gives
dflt = export(SAMPLE, os.path.join(work, "o_default"))
expect(dflt == open(os.path.join(SAMPLE, "proofs", "glb", "model.glb"), "rb").read(), "the default export is byte for byte the 2.3.0 one")

# the proofs of a delivery follow the profile: build, check and reproduce with pivots, indexing and excluded volumes
pdel = os.path.join(work, "pdelivery")
shutil.rmtree(pdel, ignore_errors=True)
shutil.copytree(SAMPLE, pdel)
shutil.copy(VARIANT, os.path.join(pdel, "ifc", "example-room-master.ifc"))
pprof = os.path.join(work, "proofs-profile.json")
json.dump({"name": "pivots-test", "version": "1.0.0", "proofs": {"glbVolumes": "exclude", "glbPivots": "placement", "glbIndexed": True}}, open(pprof, "w"))
r = py("build_proofs.py", pdel, "--profile", pprof, "--json")
expect(r.returncode == 0, "build_proofs with pivots, indexing and excluded volumes: %s" % (r.stdout + r.stderr)[-400:])
pm = open(os.path.join(pdel, "proofs", "glb", "model.glb"), "rb").read()
expect(glbkit.split_glb(pm)[0]["extras"].get("nodePivots") == "placement", "the delivered proof model is the pivoted one")
rpt.load_profile(None)
r = py("check_proofs.py", pdel, "--reproduce", "--profile", pprof, "--json")
rj = json.loads(r.stdout)
expect(not any(f["status"] == "fail" for f in rj["findings"]) and any(f["rule"] == "X-86" and f["status"] == "pass" for f in rj["findings"]),
       "check_proofs --reproduce passes (X-86 included) on the pivoted proofs: %s" % [f["message"][:120] for f in rj["findings"] if f["status"] == "fail"])

if __name__ == "__main__":
    print("test_glb_options: %s" % ("all checks behaved as expected" if not FAILS else "%d failure(s)" % len(FAILS)))
    sys.exit(1 if FAILS else 0)
