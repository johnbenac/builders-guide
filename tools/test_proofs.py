#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests of the proof tools: export_glb.py, validate_glb.py, render.py, build_proofs.py, check_proofs.py (rules X-79 to X-86) and the proof
parts of ingest.py.

    python3 tools/test_proofs.py [WORK_DIR]

Builds the sample delivery with its proofs, then checks that: the GLB files are deterministic and identical to the components ingest stores;
the validator names each of about twenty deliberately broken GLB files by its code (and Khronos validator, when installed, passes the good
ones); the renderer gives identical bytes twice and the comparison notices a changed picture; every way of breaking the proofs of a delivery
(edited picture, stale model, missing level, missing component, stray file, wrong hash, text chunk with a path, oversize picture, edited
source) is named by the right rule; the reproduction check passes on the sample and fails on an edited picture; ingest compares and links
the proofs. Requires tools/requirements.txt.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
import proofkit  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))
work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="proofs-test-")
os.makedirs(work, exist_ok=True)
FAILS = []


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FAIL", msg)


def py(script, *args):
    return subprocess.run([sys.executable, os.path.join(HERE, script), *map(str, args)], capture_output=True, text=True)


def codes(rep):
    return sorted({f.get("code") or f["rule"] for f in rep["findings"] if f["status"] in ("fail", "warn")})


def rules_failed(rep):
    return sorted({f["rule"] for f in rep["findings"] if f["status"] == "fail"})


# ------------------------------------------------------------------ the sample and its proofs
base = os.path.join(work, "base")
shutil.rmtree(base, ignore_errors=True)
r = py("make_sample_delivery.py", base)
assert r.returncode == 0, r.stdout + r.stderr
good = os.path.join(base, "example-room")
ifc = os.path.join(good, "ifc", "example-room-master.ifc")
rep = json.loads(py("check_all.py", good, "--json").stdout)
expect(rep["result"] == "pass" and any(f["source"] == "check_proofs.py" for f in rep["findings"]), "check_all.py runs check_proofs.py and the sample passes")
rep = json.loads(py("check_proofs.py", good, "--reproduce", "--json").stdout)
expect(rep["result"] == "pass" and any(f["rule"] == "X-86" and f["status"] == "pass" for f in rep["findings"]), "the sample's proofs reproduce: %s" % [f["message"] for f in rep["findings"] if f["status"] != "pass"])
man = json.load(open(os.path.join(good, "proofs", "manifest.json")))
import jsonschema  # noqa: E402
jsonschema.validate(man, json.load(open(os.path.join(ROOT, "schemas", "proofs.schema.json"))))
kinds = {}
for rr in man["renders"]:
    kinds[rr["kind"]] = kinds.get(rr["kind"], 0) + 1
expect(kinds == {"plan": 1, "interior": 4, "exterior": 4, "sheet": 6}, "render set of the sample: %s" % kinds)
expect(all(rr["glbSha256"] == next(g["sha256"] for g in man["glb"] if g["path"] == rr["glb"]) for rr in man["renders"]), "every render names the hash of its GLB")

# ------------------------------------------------------------------ export is deterministic and equals what ingest stores
e1, e2 = os.path.join(work, "e1"), os.path.join(work, "e2")
for e in (e1, e2):
    shutil.rmtree(e, ignore_errors=True)
    assert py("export_glb.py", good, "--out", e).returncode == 0
snap = lambda root: {os.path.relpath(os.path.join(b, n), root): open(os.path.join(b, n), "rb").read() for b, _, ns in os.walk(root) for n in ns}  # noqa: E731
expect(snap(e1) == snap(e2), "two exports give identical bytes")
expect(snap(e1) == {k[len("proofs/glb/"):]: v for k, v in snap(good).items() if k.startswith("proofs/glb/")}, "the delivered GLB files equal a fresh export")
sha = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731
comp_shas = {sha(v) for k, v in snap(e1).items() if k.startswith("components/")}
git = lambda *a: subprocess.run(["git", *a], cwd=repo_dir, capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
repo_dir = os.path.join(work, "repo")
shutil.rmtree(repo_dir, ignore_errors=True)
os.makedirs(os.path.join(repo_dir, "deliveries"))
shutil.copytree(good, os.path.join(repo_dir, "deliveries", "example-room"))
git("init", "-q", ".")
git("add", "-A")
subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--no-verify", "-m", "x"], cwd=repo_dir, check=True, capture_output=True)
commit = git("rev-parse", "HEAD")
out = os.path.join(work, "ing")
shutil.rmtree(out, ignore_errors=True)
p = py("ingest.py", os.path.join(repo_dir, "deliveries", "example-room"), "--commit", commit, "--out", out, "--json")
expect(p.returncode == 0, "ingest of the sample: " + p.stderr[-300:])
res = json.loads(p.stdout)
ing_geom = {c["id"][len("sha256:"):] for c in res["components"] if c["kind"] != "material-set"}
expect(comp_shas == ing_geom, "export_glb.py writes exactly the component GLB files ingest stores")
pc = res["proofs"]
expect(pc["glbMatched"] == 7 and not pc["glbMismatched"] and not pc["rendersMismatched"] and not pc["ingestGlbNotInProofs"], "ingest finds the proofs consistent: %s" % pc)
idx = json.load(open(os.path.join(out, "catalogue", "index.json")))
expect(all(any(f["role"] == "proof-render" for f in c["files"]) for c in idx["components"]), "every catalogue component links its proof render")
rec = json.load(open(os.path.join(out, res["record"])))
expect(len(rec["proofs"]["renders"]) == 15 and all(os.path.exists(os.path.join(out, r["blob"])) for r in rec["proofs"]["renders"]), "the delivery record lists and stores every render")
# a contributor's GLB that disagrees with the delivered source is reported by ingest (the ingest result stays authoritative)
tamper = os.path.join(work, "tamper")
shutil.rmtree(tamper, ignore_errors=True)
shutil.copytree(good, tamper)
mp = os.path.join(tamper, "proofs", "manifest.json")
m2 = json.load(open(mp))
m2["glb"][1]["sha256"] = "0" * 64
json.dump(m2, open(mp, "w"), indent=1)
from ingest import Store, Limits, proof_records  # noqa: E402,F401
lim = Limits(120, 0)
rec2 = proof_records(tamper, [], Store(None), lim)
expect(len(rec2["compare"]["glbMismatched"]) == 1, "ingest reports a GLB that differs from a fresh export: %s" % rec2["compare"])

# ------------------------------------------------------------------ renderer
import render  # noqa: E402
files = [{"path": os.path.join(good, "proofs", "glb", "components", n), "rel": "proofs/glb/components/" + n, "role": "component"} for n in
         sorted(os.listdir(os.path.join(good, "proofs", "glb", "components")))[:1]]
a, b = render.render_set(files), render.render_set(files)
expect(a[0]["png"] == b[0]["png"], "the same GLB renders to identical bytes twice")
stored = open(os.path.join(good, "proofs", "renders", a[0]["name"]), "rb").read()
expect(stored == a[0]["png"], "a re-render equals the delivered picture byte for byte on this toolchain")
pic = proofkit.decode_png(stored)
tol = {"meanAbsLevels": 0.5, "differingFraction": 0.001, "differenceLevels": 8}
expect(proofkit.compare_pictures(pic, pic, tol)[0], "equal pictures are within tolerance")
changed = pic.copy()
changed[100:200, 100:300] = 0
expect(not proofkit.compare_pictures(pic, changed, tol)[0], "an edited picture is outside tolerance")
chunks = proofkit.png_chunks(stored)
expect({t for t, _ in chunks} <= proofkit.RENDER_CHUNKS, "a render holds only image chunks: %s" % sorted({t.decode() for t, _ in chunks}))
big = render.render_set(files, scale=0.5)
expect(big[0]["size"][0] == 640, "--scale multiplies the size")


# ------------------------------------------------------------------ the validator
def split(data):
    jl = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + jl].decode("utf-8"))
    bl = struct.unpack("<I", data[20 + jl:24 + jl])[0]
    return doc, bytearray(data[28 + jl:28 + jl + bl])


def pack(doc, bn):
    js = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("ascii")
    js += b" " * (-len(js) % 4)
    bn = bytes(bn) + b"\0" * (-len(bn) % 4)
    return b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(bn)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bn), b"BIN\0") + bn


model = open(os.path.join(good, "proofs", "glb", "model.glb"), "rb").read()
table = open(os.path.join(good, "proofs", "glb", "components", next(n for n in os.listdir(os.path.join(good, "proofs", "glb", "components")) if n.startswith("furniture"))), "rb").read()
swatch = open(os.path.join(good, "proofs", "glb", "materials", "plaster-example.glb"), "rb").read()
import validate_glb  # noqa: E402
import report as rpt  # noqa: E402
rpt.load_profile(None)


def validate(data, role="auto", item=False, ifc_path=None):
    d = os.path.join(work, "vg")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "x.glb")
    open(p, "wb").write(data)
    return validate_glb.validate_files([{"path": p, "label": "x.glb", "role": role, "item": item, "ifc": ifc_path}], ifc_path, "off")


expect(validate(model, ifc_path=ifc)["result"] == "pass", "the good model passes (with the IFC bounding-box comparison)")
expect(validate(table)["result"] == "pass" and validate(swatch)["result"] == "pass", "the good component and swatch pass")


def edit_json(fn, src=model):
    doc, bn = split(src)
    fn(doc, bn)
    return pack(doc, bn)


def set_path(doc, *keys, value):
    for k in keys[:-1]:
        doc = doc[k]
    doc[keys[-1]] = value


bad = {
    "truncated": (model[:200], "GLB-CONTAINER"),
    "not a glb": (b"hello world, not a model" * 3, "GLB-CONTAINER"),
    "external uri": (edit_json(lambda d, b: d["buffers"][0].update(uri="http://example.invalid/x.bin")), "GLB-URI"),
    "units": (edit_json(lambda d, b: d["extras"].update(units="feet")), "GLB-UNITS"),
    "no axis note": (edit_json(lambda d, b: d["extras"].pop("axisConversion")), "GLB-AXES"),
    "unused material": (edit_json(lambda d, b: d["materials"].append({"pbrMetallicRoughness": {}})), "GLB-UNUSED"),
    "unused accessor": (edit_json(lambda d, b: d["accessors"].append({"bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC3"})), "GLB-UNUSED"),
    "index out of range": (edit_json(lambda d, b: d["nodes"][2].update(mesh=999)), "GLB-INDEX"),
    "wrong min/max": (edit_json(lambda d, b: d["accessors"][0].update(max=[99.0, 99.0, 99.0])), "GLB-MINMAX"),
    "wrong generator": (edit_json(lambda d, b: d["asset"].update(generator="exporter on a machine")), "GLB-GENERATOR"),
    "bad node name": (edit_json(lambda d, b: d["nodes"][2].update(name="chair")), "GLB-NAMES"),
    "bad root name": (edit_json(lambda d, b: d["nodes"][0].update(name="scene")), "GLB-NAMES"),
    "required extension": (edit_json(lambda d, b: d.update(extensionsRequired=["KHR_draco_mesh_compression"], extensionsUsed=["KHR_draco_mesh_compression"])), "GLB-EXTENSION"),
    "node cycle": (edit_json(lambda d, b: d["nodes"][1].update(children=[0])), "GLB-NODE"),
    "scene missing": (edit_json(lambda d, b: d.pop("scene")), "GLB-SCENE"),
    "bad version": (edit_json(lambda d, b: d["asset"].update(version="1.0")), "GLB-VERSION"),
    "stray top-level key": (edit_json(lambda d, b: d.update(secrets={"a": 1})), "GLB-TOPLEVEL"),
    "buffer length": (edit_json(lambda d, b: d["buffers"][0].update(byteLength=10 ** 6)), "GLB-BUFFER"),
    "extras bounds wrong": (edit_json(lambda d, b: d["extras"]["bounds"].update(max=[500.0, 500.0, 500.0])), "GLB-BOUNDS"),
    "no extras levels": (edit_json(lambda d, b: d["extras"].pop("levels")), "GLB-EXTRAS"),
}


def scale_positions(factor):
    def fn(d, b):
        acc = d["accessors"][0]
        bv = d["bufferViews"][acc["bufferView"]]
        n = acc["count"] * 3
        arr = list(struct.unpack("<%df" % n, bytes(b[bv["byteOffset"]:bv["byteOffset"] + n * 4])))
        arr = [x * factor for x in arr]
        b[bv["byteOffset"]:bv["byteOffset"] + n * 4] = struct.pack("<%df" % n, *arr)
        acc["min"] = [min(arr[i::3]) for i in range(3)]
        acc["max"] = [max(arr[i::3]) for i in range(3)]
    return fn


def scale_normals(d, b):
    for pr in d["meshes"][0]["primitives"]:
        acc = d["accessors"][pr["attributes"]["NORMAL"]]
        bv = d["bufferViews"][acc["bufferView"]]
        n = acc["count"] * 3
        arr = [x * 3.0 for x in struct.unpack("<%df" % n, bytes(b[bv["byteOffset"]:bv["byteOffset"] + n * 4]))]
        b[bv["byteOffset"]:bv["byteOffset"] + n * 4] = struct.pack("<%df" % n, *arr)


def flip_normals(d, b):
    for pr in d["meshes"][0]["primitives"]:
        acc = d["accessors"][pr["attributes"]["NORMAL"]]
        bv = d["bufferViews"][acc["bufferView"]]
        n = acc["count"] * 3
        arr = [-x for x in struct.unpack("<%df" % n, bytes(b[bv["byteOffset"]:bv["byteOffset"] + n * 4]))]
        b[bv["byteOffset"]:bv["byteOffset"] + n * 4] = struct.pack("<%df" % n, *arr)


def nan_position(d, b):
    acc = d["accessors"][0]
    bv = d["bufferViews"][acc["bufferView"]]
    b[bv["byteOffset"]:bv["byteOffset"] + 4] = struct.pack("<f", float("nan"))


bad["wrong unit (x1000000)"] = (edit_json(scale_positions(1000000.0), model), "GLB-EXTENT")
bad["normals not unit"] = (edit_json(scale_normals, table), "GLB-NORMAL")
bad["normals against winding"] = (edit_json(flip_normals, table), "GLB-NORMAL-FACING")
bad["NaN position"] = (edit_json(nan_position, table), "GLB-NONFINITE")
bad["swatch without uv"] = (edit_json(lambda d, b: d["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0"), swatch), "GLB-TEXCOORD")
bad["swatch image is a uri"] = (edit_json(lambda d, b: d["images"][0].update(uri="albedo.png") or d["images"][0].pop("bufferView"), swatch), "GLB-URI")
bad["swatch unused image"] = (edit_json(lambda d, b: d["images"].append(dict(d["images"][0])), swatch), "GLB-UNUSED")
bad["swatch image not png"] = (edit_json(lambda d, b: d["images"][0].update(mimeType="image/jpeg"), swatch), "GLB-IMAGE")
bad["swatch tangent w"] = (edit_json(lambda d, b: b.__setitem__(slice(d["bufferViews"][2]["byteOffset"] + 12, d["bufferViews"][2]["byteOffset"] + 16), struct.pack("<f", 0.5)), swatch), "GLB-TANGENT")
for name, (data, code) in bad.items():
    rep = validate(data, role="model" if not name.startswith(("swatch", "normals", "NaN")) else "auto")
    expect(rep["result"] == "fail" and code in codes(rep), "validator: %s should give %s, got %s" % (name, code, codes(rep)))
    expect(all(f["rule"] == "X-80" and f.get("fix_hint") for f in rep["findings"] if f["status"] == "fail"), "validator: %s findings carry rule X-80 and a fix hint" % name)
rep = validate(table, item=True)
expect(rep["result"] == "pass", "an item within the triangle budget passes")
# a moved vertex in the model is found by the comparison with the IFC file
doc, bn = split(model)
node = next(n for n in doc["nodes"] if n.get("mesh") is not None)
acc = doc["accessors"][doc["meshes"][node["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
bv = doc["bufferViews"][acc["bufferView"]]
x0 = struct.unpack("<f", bytes(bn[bv["byteOffset"]:bv["byteOffset"] + 4]))[0]
arr = list(struct.unpack("<%df" % (acc["count"] * 3), bytes(bn[bv["byteOffset"]:bv["byteOffset"] + acc["count"] * 12])))
arr = [x + 0.5 if i % 3 == 0 else x for i, x in enumerate(arr)]
bn[bv["byteOffset"]:bv["byteOffset"] + acc["count"] * 12] = struct.pack("<%df" % len(arr), *arr)
acc["min"] = [min(arr[i::3]) for i in range(3)]
acc["max"] = [max(arr[i::3]) for i in range(3)]
rep = validate(pack(doc, bn), ifc_path=ifc)
expect("GLB-BBOX-IFC" in codes(rep), "a node moved by 0.5 m is found by the IFC bounding-box comparison: %s" % codes(rep))
k = validate_glb.khronos([os.path.join(good, "proofs", "glb", "model.glb")])
if k[0]:
    expect(k[1] and list(k[1].values())[0]["errors"] == 0, "the Khronos glTF Validator finds no error in the model")
    kb = os.path.join(work, "vg", "k.glb")
    open(kb, "wb").write(bad["wrong min/max"][0])
    expect(list(validate_glb.khronos([kb])[1].values())[0]["errors"] > 0, "the Khronos validator also flags a broken file")
else:
    print("Khronos glTF Validator not installed: that part skipped (npm ci --prefix tools/khronos)")


# the tolerant comparison used when the library version or processor architecture differs from the one the proofs were made with
import check_proofs  # noqa: E402
expect(check_proofs.glb_close(model, model)[0], "glb_close: identical files agree")
expect(check_proofs.glb_close(model, edit_json(scale_positions(1.00001)))[0], "glb_close: a difference of about 0.05 mm is accepted")
expect(not check_proofs.glb_close(model, edit_json(scale_positions(1.01)))[0], "glb_close: a difference of centimetres is refused")
expect(not check_proofs.glb_close(model, edit_json(lambda d, b: d["nodes"][2].update(name="structure:Other#X")))[0], "glb_close: a renamed node is refused")
expect(not check_proofs.glb_close(model, table)[0], "glb_close: different models are refused")

# ------------------------------------------------------------------ the checks on a delivery
def variant(name, mutate, profile=None, reproduce=False):
    d = os.path.join(work, "v-" + name, "example-room")
    shutil.rmtree(os.path.dirname(d), ignore_errors=True)
    shutil.copytree(good, d)
    mutate(d)
    args = [d, "--json"] + (["--reproduce"] if reproduce else []) + (["--profile", profile] if profile else [])
    p = py("check_proofs.py", *args)
    return json.loads(p.stdout), p.returncode


def manifest_edit(fn):
    def m(d):
        p = os.path.join(d, "proofs", "manifest.json")
        doc = json.load(open(p))
        fn(doc)
        json.dump(doc, open(p, "w"), indent=1)
    return m


def refresh(d, path):
    """Update the manifest entry of a changed file (hash and size), as someone who edits a file and tidies the manifest would."""
    p = os.path.join(d, "proofs", "manifest.json")
    doc = json.load(open(p))
    data = open(os.path.join(d, path), "rb").read()
    for row in doc["renders"] + doc["glb"]:
        if row["path"] == path:
            row["sha256"], row["bytes"] = sha(data), len(data)
    json.dump(doc, open(p, "w"), indent=1)


def with_text_chunk(png, key, value):
    ch = proofkit.png_chunks(png)
    body = b"\x89PNG\r\n\x1a\n"
    for t, payload in ch:
        if t == b"IEND":
            tp = key.encode() + b"\0" + value.encode()
            body += struct.pack(">I", len(tp)) + b"tEXt" + tp + struct.pack(">I", zlib.crc32(b"tEXt" + tp) & 0xFFFFFFFF)
        body += struct.pack(">I", len(payload)) + t + payload + struct.pack(">I", zlib.crc32(t + payload) & 0xFFFFFFFF)
    return body


def edit_render_text(d):
    path = "proofs/renders/exterior-0.png"
    data = open(os.path.join(d, path), "rb").read()
    open(os.path.join(d, path), "wb").write(with_text_chunk(data, "Comment", "made in /" + "home/someone/work"))
    refresh(d, path)


def edit_render_pixels(d):
    from PIL import Image
    import numpy as np
    path = "proofs/renders/exterior-1.png"
    arr = np.array(Image.open(os.path.join(d, path)).convert("RGB"))
    arr[100:400, 200:700] = (200, 30, 30)
    Image.fromarray(arr).save(os.path.join(d, path), compress_level=9)
    refresh(d, path)


def drop_render(match):
    def m(d):
        def fn(doc):
            gone = [r for r in doc["renders"] if match(r)]
            doc["renders"] = [r for r in doc["renders"] if not match(r)]
            for r in gone:
                os.remove(os.path.join(d, r["path"]))
        manifest_edit(fn)(d)
    return m


def wrong_glb_hash(doc):
    doc["renders"][3]["glbSha256"] = "1" * 64


def append_ifc(d):
    with open(os.path.join(d, "ifc", "example-room-master.ifc"), "a") as fh:
        fh.write("\n")


def stray(d):
    open(os.path.join(d, "proofs", "notes.md"), "w").write("x")


def remove_all(d):
    shutil.rmtree(os.path.join(d, "proofs"))


def corrupt_glb(d):
    p = os.path.join(d, "proofs", "glb", "model.glb")
    data = bytearray(open(p, "rb").read())
    data[-5] ^= 0xFF
    open(p, "wb").write(bytes(data))


def drop_component(d):
    def fn(doc):
        gone = next(g for g in doc["glb"] if g["role"] == "component")
        doc["glb"] = [g for g in doc["glb"] if g is not gone]
        doc["renders"] = [r for r in doc["renders"] if r["glb"] != gone["path"]]
        doc["coverage"]["components"] = [c for c in doc["coverage"]["components"] if c["glb"] != gone["path"]]
        for r in (gone["path"],):
            os.remove(os.path.join(d, r))
        for f in os.listdir(os.path.join(d, "proofs", "renders")):
            if f.startswith("sheet-") and gone["path"].split("/")[-1][:-4] in f:
                os.remove(os.path.join(d, "proofs", "renders", f))
    manifest_edit(fn)(d)


def failing_report(d):
    p = os.path.join(d, "proofs", "reports", "glb-validation.json")
    rep = json.load(open(p))
    rep["result"] = "fail"
    rep["summary"]["requiredFailures"] = 1
    json.dump(rep, open(p, "w"), indent=1)
    refresh_validation(d)


def refresh_validation(d):
    p = os.path.join(d, "proofs", "manifest.json")
    doc = json.load(open(p))
    data = open(os.path.join(d, doc["validation"]["path"]), "rb").read()
    doc["validation"]["sha256"], doc["validation"]["bytes"] = sha(data), len(data)
    json.dump(doc, open(p, "w"), indent=1)


def seq(*fns):
    return lambda d: [f(d) for f in fns]


tight = os.path.join(work, "tight-profile.json")
json.dump({"name": "tight", "version": "1.0.0", "proofs": {"maxRenderPixels": 100000, "maxRenderBytes": 1000, "minRenderWidth": 4000}}, open(tight, "w"))
cases = [
    ("no proofs at all", remove_all, None, "X-79"),
    ("stray file in proofs", stray, None, "X-79"),
    ("edited render, manifest not updated", lambda d: open(os.path.join(d, "proofs", "renders", "exterior-2.png"), "ab").write(b"x"), None, "X-79"),
    ("glb edited, manifest not updated", corrupt_glb, None, "X-79"),
    ("manifest names another delivery", manifest_edit(lambda doc: doc["delivery"].update(id="other-room")), None, "X-79"),
    ("manifest not matching the schema", manifest_edit(lambda doc: doc.pop("coverage")), None, "X-79"),
    ("source IFC changed after the proofs", append_ifc, None, "X-81"),
    ("a component without a GLB", drop_component, None, "X-81"),
    ("validation report that fails", failing_report, None, "X-81"),
    ("no plan for the level", drop_render(lambda r: r["kind"] == "plan"), None, "X-82"),
    ("too few interior views", drop_render(lambda r: r["kind"] == "interior" and r["id"].endswith("-3")), None, "X-82"),
    ("no exterior views", drop_render(lambda r: r["kind"] == "exterior"), None, "X-82"),
    ("no sheet for a component", drop_render(lambda r: r["kind"] == "sheet" and "table" in r["id"]), None, "X-82"),
    ("render names the wrong GLB hash", manifest_edit(wrong_glb_hash), None, "X-83"),
    ("render of a GLB not in the delivery", manifest_edit(lambda doc: doc["renders"][0].update(glb="proofs/glb/other.glb")), None, "X-83"),
    ("text chunk with a path in a render", edit_render_text, None, "X-85"),
    ("pixel and size limits", lambda d: None, tight, "X-84"),
]
for name, mutate, profile, rule in cases:
    rep, code = variant(name.replace(" ", "-"), mutate, profile)
    expect(code == 1 and rule in rules_failed(rep), "check_proofs: %s should fail %s, got %s" % (name, rule, rules_failed(rep)))
    expect(all(f.get("fix_hint") for f in rep["findings"] if f["status"] == "fail"), "check_proofs: %s findings carry a fix hint" % name)
rep, code = variant("edited-pixels-stored", edit_render_pixels, None)
expect(code == 0, "an edited picture with a tidied manifest passes the stored checks (only the reproduction can see it): %s" % rules_failed(rep))
rep, code = variant("edited-pixels", edit_render_pixels, None, reproduce=True)
expect(code == 1 and "X-86" in rules_failed(rep), "--reproduce notices a picture that was edited (X-86): %s" % rules_failed(rep))
rep, code = variant("append-ifc-reproduce", append_ifc, None, reproduce=True)
expect(code == 1, "--reproduce on a changed source fails")
rep, code = variant("clean-reproduce", lambda d: None, None, reproduce=True)
expect(code == 0, "--reproduce passes on the untouched sample")

# the rule is skipped, not passed, when the toolchain is missing
env = dict(os.environ, PYTHONPATH="")
code_snip = ("import sys; sys.modules['ifcopenshell'] = None; sys.argv = ['check_proofs.py', sys.argv[1], '--reproduce', '--json']; "
             "sys.path.insert(0, %r); import runpy; runpy.run_path(%r, run_name='__main__')" % (HERE, os.path.join(HERE, "check_proofs.py")))
p = subprocess.run([sys.executable, "-c", code_snip, good], capture_output=True, text=True, env=env)
try:
    rep = json.loads(p.stdout)
    skipped = [f for f in rep["findings"] if f["rule"] == "X-86"]
    expect(skipped and all(f["status"] == "info" for f in skipped) and "skipped" in skipped[0]["message"], "X-86 is reported as skipped (info), not passed, when the toolchain is missing: %s" % skipped)
except ValueError:
    expect(False, "check_proofs without ifcopenshell printed no report: " + p.stderr[-300:])

# check_all and the CI runner see the proofs
d = os.path.join(work, "v-ci", "example-room")
shutil.rmtree(os.path.dirname(d), ignore_errors=True)
shutil.copytree(good, d)
stray(d)
rep = json.loads(py("check_all.py", d, "--json").stdout)
expect(rep["result"] == "fail" and any(f["rule"] == "X-79" and f["status"] == "fail" for f in rep["findings"]), "check_all.py fails a delivery whose proofs are wrong")

# ------------------------------------------------------------------ nothing personal or local in the proofs
bad_hits = []
for rel, data in snap(good).items():
    if rel.startswith("proofs/") and rel.endswith(".json"):
        for kind, ex in proofkit.find_leaks(data.decode("utf-8")):
            bad_hits.append((rel, kind, ex))
    elif rel.startswith("proofs/") and rel.endswith(".glb"):
        for ptr, text in proofkit.walk_strings(glbkit.split_glb(data)[0]):
            bad_hits += [(rel, kind, ex) for kind, ex in proofkit.find_leaks(text)]
    elif rel.startswith("proofs/") and rel.endswith(".png"):
        bad_hits += [(rel, "metadata", m) for m in proofkit.image_metadata_problems(data, True)]
expect(not bad_hits, "the sample's proofs hold no path, address or e-mail: %s" % bad_hits[:3])
for s_, d_ in (("file" + ":///x", "local-file address"), ("/" + "home/a/b", "absolute path"), ("C:\\Users\\a", "drive-letter path"), ("a.b@c.example", "e-mail address"), ("10.1.2.3", "IPv4 address"),
               ("https://host.example/x", "address with a host")):
    expect(any(k == d_ for k, _ in proofkit.find_leaks(s_)), "find_leaks sees a %s" % d_)
expect(not proofkit.find_leaks("tools/render.py and 2.3.0 and (x,y,z) -> (x,z,-y)"), "find_leaks passes clean text")
exif = b"\xff\xd8\xff\xe1\x00\x08Exif\0\0\xff\xd9"
expect(proofkit.image_metadata_problems(exif, False), "a JPEG with an EXIF block is refused")

if FAILS:
    print("test_proofs: FAIL (%d)" % len(FAILS))
    sys.exit(1)
print("test_proofs: all checks behaved as expected (%d broken GLB files, %d broken proof sets)" % (len(bad), len(cases) + 3))
