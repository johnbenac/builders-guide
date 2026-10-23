#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests of the submission checks (check_submission.py, rules X-70 to X-78) and of the ingest tool (ingest.py).

    python3 tools/test_submission.py [WORK_DIR]

Builds the sample delivery in a temporary folder, then: breaks it in the ways a contributor (or an attacker) could and checks that the
right rule names each break; ingests it and checks the catalogue, the hashes, the deduplication, the determinism, the refusals (altered
file, link, wrong commit, dirty work tree, time limit) and that nothing is written by a dry run or sent anywhere.

Requires: pip install -r tools/requirements.txt (and requirements-preview.txt, used to draw the sample's preview picture)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ingest  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))
work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="submission-test-")
os.makedirs(work, exist_ok=True)
FAILS = []


def expect(cond, msg):
    if not cond:
        FAILS.append(msg)
        print("FAIL", msg)


def py(script, *args, cwd=None):
    return subprocess.run([sys.executable, os.path.join(HERE, script), *map(str, args)], capture_output=True, text=True, cwd=cwd)


def required(rep):
    return sorted({f["rule"] for f in rep["findings"] if f["status"] == "fail"})


def check(path, profile=None):
    p = py("check_submission.py", path, "--json", *(["--profile", profile] if profile else []))
    return json.loads(p.stdout), p.returncode


# ------------------------------------------------------------------ the sample delivery
base_dir = os.path.join(work, "base")
shutil.rmtree(base_dir, ignore_errors=True)
r = py("make_sample_delivery.py", base_dir)
assert r.returncode == 0, r.stdout + r.stderr
good = os.path.join(base_dir, "example-room")
rep, code = check(good)
expect(code == 0 and required(rep) == [], "the sample delivery should pass check_submission: %s" % required(rep))
whole = json.loads(py("check_all.py", good, "--json").stdout)
expect(whole["result"] == "pass" and any(f["source"] == "check_submission.py" for f in whole["findings"]), "check_all.py runs check_submission.py on a delivery")
committed = os.path.join(ROOT, "deliveries", "example-room")
if os.path.isdir(committed):
    expect(check(committed)[1] == 0, "deliveries/example-room should pass check_submission")


def variant(name, mutate):
    d = os.path.join(work, "v-" + name, "example-room")
    shutil.rmtree(os.path.dirname(d), ignore_errors=True)
    shutil.copytree(good, d, symlinks=True)
    mutate(d)
    return d


def edit_manifest(fn):
    def m(d):
        p = os.path.join(d, "delivery.json")
        doc = json.load(open(p))
        fn(doc)
        json.dump(doc, open(p, "w"), indent=2)
    return m


def write(rel, data, mode="wb"):
    def m(d):
        os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True)
        with open(os.path.join(d, rel), mode) as fh:
            fh.write(data)
    return m


def link(d):
    os.symlink("/etc/hostname", os.path.join(d, "notes", "link.md"))


def dirlink(d):
    os.symlink("..", os.path.join(d, "notes", "up"))


def execbit(d):
    os.chmod(os.path.join(d, "notes", "changes.md"), 0o755)


def seq(*fns):
    return lambda d: [f(d) for f in fns]


def corrupt_png(d):
    open(os.path.join(d, "previews", "iso.png"), "wb").write(b"not an image at all")


def huge_png(d):
    import struct
    import zlib
    ihdr = struct.pack(">IIBBBBB", 40000, 40000, 8, 0, 0, 0, 0)
    body = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    open(os.path.join(d, "previews", "iso.png"), "wb").write(body)


def fake_glb(d):
    open(os.path.join(d, "previews", "model.glb"), "wb").write(b"glTF\x02\x00\x00\x00" + b"\x00" * 20)


cases = [
    ("a program", write("notes/run.sh", b"#!/bin/sh\necho hi\n"), "X-72"),
    ("an archive", write("notes/more.zip", b"PK\x03\x04" + b"\0" * 30), "X-72"),
    ("a python script", write("tools.py", b"print(1)\n"), "X-72"),
    ("double extension", write("notes/a.png.exe", b"MZ"), "X-72"),
    ("no extension", write("notes/README", b"x"), "X-72"),
    ("executable bit", execbit, "X-72"),
    ("symbolic link", link, "X-75"),
    ("folder link", dirlink, "X-75"),
    ("case collision", seq(write("notes/Note.md", b"a"), write("notes/note.md", b"b")), "X-74"),
    ("space in a name", write("notes/my notes.md", b"a"), "X-74"),
    ("leading dot", write("notes/.hidden.md", b"a"), "X-74"),
    ("reserved name", write("notes/con.md", b"a"), "X-74"),
    ("long path", write("notes/" + "a" * 90 + "/" + "b" * 90 + "/" + "c" * 30 + ".md", b"a"), "X-74"),
    ("parent path in the manifest", edit_manifest(lambda m: m["files"].append({"path": "../outside.png", "role": "other", "sha256": "0" * 64, "bytes": 0})), "X-74"),
    ("absolute path in the manifest", edit_manifest(lambda m: m["files"].append({"path": "/etc/passwd", "role": "other", "sha256": "0" * 64, "bytes": 0})), "X-74"),
    ("backslash path in the manifest", edit_manifest(lambda m: m["files"].append({"path": "a\\b.png", "role": "other", "sha256": "0" * 64, "bytes": 0})), "X-74"),
    ("text named png", corrupt_png, "X-77"),
    ("decompression bomb header", huge_png, "X-77"),
    ("fake glb", fake_glb, "X-77"),
    ("json that does not parse", write("notes/data.json", b"{nope"), "X-77"),
    ("script tag in markdown", write("notes/x.md", b"<script>alert(1)</script>"), "X-77"),
    ("not utf-8", write("notes/x.md", b"\xff\xfe\x00"), "X-77"),
    ("ifc that is not", write("ifc/other.ifc", b"hello"), "X-77"),
    ("other licence", edit_manifest(lambda m: m["submission"].update(licence="All-Rights-Reserved")), "X-71"),
    ("missing attestation", edit_manifest(lambda m: m["submission"]["attestation"].update(noRestrictedContent=False)), "X-76"),
    ("no submission block", edit_manifest(lambda m: m.pop("submission")), "X-70"),
    ("slug differs from id", edit_manifest(lambda m: m["delivery"].update(id="other-id")), "X-70"),
    ("no handle", edit_manifest(lambda m: m["submission"]["submitter"].pop("handle")), "X-70"),
]
for name, fn, rule in cases:
    rep, code = check(variant(name.replace(" ", "-"), fn))
    expect(rule in required(rep) and code == 1, "%s: expected %s, got %s (exit %d)" % (name, rule, required(rep), code))
    expect(all("fix_hint" in f for f in rep["findings"] if f["status"] == "fail"), "%s: findings carry a fix hint" % name)

# a rule is warn-level when the profile lowers it; limits come from the profile
small = os.path.join(work, "small-profile.json")
json.dump({"format": "profile/1", "name": "small", "version": "1.0.0", "submission": {"maxFiles": 5, "maxFileBytes": 100000, "maxDeliveryBytes": 200000}}, open(small, "w"))
rep, code = check(good, small)
expect("X-73" in required(rep), "limits of the profile apply (X-73)")
low = os.path.join(work, "low-profile.json")
json.dump({"format": "profile/1", "name": "low", "version": "1.0.0", "ruleLevels": {"X-72": "recommended"}}, open(low, "w"))
rep, code = check(variant("lowered", write("notes/run.sh", b"#!/bin/sh\n")), low)
expect(code == 0 and any(f["rule"] == "X-72" and f["status"] == "warn" for f in rep["findings"]), "a profile can lower X-72 to a warning")
rep, code = check(variant("nopreview", lambda d: (os.remove(os.path.join(d, "previews", "iso.png")), os.remove(os.path.join(d, "SHA256SUMS.txt")))))
expect(any(f["rule"] == "X-78" and f["status"] == "warn" for f in rep["findings"]), "no preview gives X-78 as a warning")
p = py("check_submission.py", os.path.join(work, "does-not-exist"), "--json")
expect(p.returncode == 3, "a missing folder exits 3")
print("check_submission: %d broken deliveries named by the right rule" % len(cases))

# ------------------------------------------------------------------ GLB writer and reader
import numpy as np  # noqa: E402
tri = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [0, 1, 1]], dtype=float)
g1 = ingest.write_glb([((0.5, 0.5, 0.5, 1.0), tri)])
g2 = ingest.write_glb([((0.5, 0.5, 0.5, 1.0), tri.copy())])
expect(g1 == g2 and len(g1) % 4 == 0, "write_glb is deterministic and aligned")
info = ingest.read_glb(g1)
expect(info["triangles"] == 2 and info["min"] == [0.0, 0.0, -1.0] and info["max"] == [1.0, 1.0, 0.0], "GLB axes are converted to Y up: %s" % info)
for bad in (g1[:-4], b"glTF" + g1[4:8] + b"\x00\x00\x00\x00" + g1[12:], g1.replace(b"BIN\0", b"BAD\0")):
    try:
        ingest.read_glb(bad)
        expect(False, "read_glb accepted a damaged GLB")
    except ingest.Failed:
        pass
try:
    import trimesh
    s = trimesh.load(__import__("io").BytesIO(g1), file_type="glb")
    expect(sum(len(m.faces) for m in s.geometry.values()) == 2, "an independent glTF reader loads the GLB")
    print("trimesh loaded the GLB written by ingest.py")
except ImportError:
    print("trimesh not installed: independent GLB read skipped")

# ------------------------------------------------------------------ a git repository holding the delivery, the way a merged commit looks
repo = os.path.join(work, "repo")
shutil.rmtree(repo, ignore_errors=True)
os.makedirs(os.path.join(repo, "deliveries"))
shutil.copytree(good, os.path.join(repo, "deliveries", "example-room"))


def git(*a, cwd=repo):
    r_ = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *a], cwd=cwd, capture_output=True, text=True)
    assert r_.returncode == 0, r_.stderr
    return r_.stdout.strip()


git("init", "-q", "--template=", "-b", "main")
git("add", "-A")
git("commit", "-q", "-m", "add delivery")
C1 = git("rev-parse", "HEAD")
D = os.path.join(repo, "deliveries", "example-room")
out = os.path.join(work, "out")
shutil.rmtree(out, ignore_errors=True)


def ing(*args, delivery=D, commit=C1):
    return py("ingest.py", delivery, "--commit", commit, *args)


p = ing("--dry-run", "--json")
expect(p.returncode == 0, "dry run exits 0: " + p.stderr[-300:])
dry = json.loads(p.stdout)
expect(not os.path.exists(out), "a dry run writes nothing")
expect(dry["summary"]["components"] == 7 and dry["summary"]["uniqueComponents"] == 6, "the sample splits into 7 components, 6 unique: %s" % dry["summary"])
kinds = sorted(c["kind"] for c in dry["components"])
expect(kinds == ["covering", "door", "fixture", "furniture", "furniture", "material-set", "window"], "component kinds: %s" % kinds)
expect(dry["commitVerified"] is True, "commit verified against the work tree")
p = ing("--out", out, "--json")
expect(p.returncode == 0, "ingest exits 0: " + p.stderr[-300:])
res = json.loads(p.stdout)
expect(res["summary"] == dry["summary"], "dry run and real run agree")
idx = json.load(open(os.path.join(out, "catalogue", "index.json")))
expect(len(idx["components"]) == 6, "six unique components in the index")
for c in idx["components"]:
    for f in c["files"]:
        data = open(os.path.join(out, f["blob"]), "rb").read()
        expect(hashlib.sha256(data).hexdigest() == f["sha256"] == re.search(r"([0-9a-f]{64})\.", f["blob"]).group(1) and len(data) == f["bytes"], "blob hash %s" % f["blob"])
        if f["role"] == "geometry":
            gi = ingest.read_glb(data)
            expect(gi["triangles"] == c["geometry"]["triangles"], "GLB triangles match the catalogue for %s" % c["name"])
    expect(c["id"] == "sha256:" + next(f["sha256"] for f in c["files"] if f["role"] in ("geometry", "descriptor")), "component id is the primary file hash")
table = next(c for c in idx["components"] if c["category"] == "table")
expect(len(table["occurrences"]) == 2 and {o["sourcePath"] for o in table["occurrences"]} == {"ifc/example-room-master.ifc", "items/table.work.1600/table.work.1600.ifc"},
       "the table from the item and from the master is one component with two occurrences")
expect(abs(table["geometry"]["dimensions"]["x"] - 1.6) < 1e-6 and abs(table["geometry"]["dimensions"]["z"] - 0.74) < 1e-6, "table dimensions")
expect(all(o["commit"] == C1 and o["submitter"] == "example-contributor" and o["licence"] == "CC-BY-4.0" for c in idx["components"] for o in c["occurrences"]),
       "every occurrence carries delivery, commit, submitter and licence")
expect(any(r["sets"] and r["sets"][0]["component"] for c in idx["components"] for r in c.get("materialRefs", [])), "materials link to the material-set component")
try:
    import jsonschema
    sch = json.load(open(os.path.join(ROOT, "schemas", "catalogue.schema.json")))
    for rel in ["catalogue/index.json", res["record"], res["handoff"]]:
        jsonschema.validate(json.load(open(os.path.join(out, rel))), sch)
except ImportError:
    pass
hand = json.load(open(os.path.join(out, res["handoff"])))
expect(hand["uploaded"] is False and hand["counts"]["blobsNew"] == len(hand["blobsToPublish"]), "handoff manifest lists the new blobs and says nothing was uploaded")

# determinism: a second output folder is byte-identical, and a second run into the same folder changes nothing
out2 = os.path.join(work, "out2")
shutil.rmtree(out2, ignore_errors=True)
expect(ing("--out", out2).returncode == 0, "second ingest")
snap = lambda root: {os.path.relpath(os.path.join(b, n), root): open(os.path.join(b, n), "rb").read() for b, _, ns in os.walk(root) for n in ns}  # noqa: E731
expect(snap(out) == snap(out2), "two ingests of the same commit give byte-identical output")
before = snap(out)
p = ing("--out", out, "--json")
expect(snap(out) == before and json.loads(p.stdout)["summary"]["blobsNew"] == 0, "ingesting again into the same folder changes nothing")

# deduplication across deliveries: the same bytes under another slug and commit add occurrences, not blobs
d2 = os.path.join(repo, "deliveries", "second-room")
shutil.copytree(D, d2)
doc = json.load(open(os.path.join(d2, "delivery.json")))
doc["delivery"]["id"] = "second-room"
doc["submission"]["submitter"]["handle"] = "another-contributor"
doc["submission"]["licence"] = "CC0-1.0"
for key in ("files", "format"):
    doc.pop(key)
meta = os.path.join(work, "second-meta.json")
json.dump(doc, open(meta, "w"))
os.remove(os.path.join(d2, "delivery.json"))
os.remove(os.path.join(d2, "SHA256SUMS.txt"))
assert py("build_package.py", "init", d2, meta, "--manifest-name", "delivery.json").returncode == 0
git("add", "-A")
git("commit", "-q", "-m", "add second delivery")
C2 = git("rev-parse", "HEAD")
n_blobs = len(os.listdir(os.path.join(out, "blobs", "sha256")))
p = ing("--out", out, "--json", delivery=d2, commit=C2)
expect(p.returncode == 0, "second delivery ingests: " + p.stderr[-300:])
r2 = json.loads(p.stdout)
expect(r2["summary"]["blobsNew"] <= 2, "second delivery stores only its own manifest blobs, got %d new" % r2["summary"]["blobsNew"])
idx = json.load(open(os.path.join(out, "catalogue", "index.json")))
expect(len(idx["components"]) == 6 and len(idx["deliveries"]) == 2, "the catalogue still has six unique components and now two deliveries")
table = next(c for c in idx["components"] if c["category"] == "table")
expect(len(table["occurrences"]) == 4 and {o["licence"] for o in table["occurrences"]} == {"CC-BY-4.0", "CC0-1.0"}, "occurrences keep their own licence and commit")
expect(all(c["alreadyInCatalogue"] for c in r2["components"]), "every component of the second delivery was already in the catalogue")
print("ingest: %d components, %d blobs (%d before the second delivery)" % (len(idx["components"]), len(os.listdir(os.path.join(out, "blobs", "sha256"))), n_blobs))

# refusals
expect(ing("--dry-run", commit="abc").returncode == 1, "a short commit hash is refused")
expect(ing("--dry-run", commit="0" * 40).returncode == 1, "a commit that is not HEAD is refused")
p = py("ingest.py", D, "--commit", C1, "--dry-run", "--require-ancestor-of", "main")
expect(p.returncode == 1, "HEAD is C2 now, so C1 is not what is checked out: refused")
p = py("ingest.py", D, "--commit", C2, "--dry-run", "--require-ancestor-of", "main")
expect(p.returncode == 0, "the commit on main passes --require-ancestor-of main: " + p.stderr[-200:])
p = py("ingest.py", D, "--commit", C2, "--dry-run", "--require-ancestor-of", "no-such-branch")
expect(p.returncode == 1, "an unknown ref is refused")
open(os.path.join(D, "notes", "changes.md"), "a").write("edit\n")
p = ing("--dry-run", commit=C2)
expect(p.returncode == 1 and "differs from the commit" in p.stderr, "an uncommitted change is refused: " + p.stderr[-200:])
git("checkout", "--", ".")
os.symlink("/etc/hostname", os.path.join(D, "notes", "l.md"))
p = ing("--dry-run", commit=C2)
expect(p.returncode == 1, "a delivery with a link is refused")
os.remove(os.path.join(D, "notes", "l.md"))
tam = variant("tampered", lambda d: open(os.path.join(d, "ifc", "example-room-master.ifc"), "ab").write(b"\n/* x */\n"))
p = py("ingest.py", tam, "--commit", "1" * 40, "--dry-run")
expect(p.returncode == 1, "a delivery whose file no longer matches its hash is refused (exit %d)" % p.returncode)
p = py("ingest.py", tam, "--commit", "1" * 40, "--dry-run")
expect(not os.path.exists(os.path.join(work, "v-tampered", "blobs")), "a refused ingest leaves nothing behind")
p = py("ingest.py", good, "--commit", "2" * 40, "--dry-run", "--max-seconds", "1")
expect(p.returncode == 3 and "time limit" in p.stderr, "a one second limit stops the run (exit %d): %s" % (p.returncode, p.stderr[-120:]))
p = py("ingest.py", good, "--commit", "2" * 40, "--json")
expect(p.returncode == 2, "--out is required without --dry-run")
p = py("ingest.py", good, "--commit", "2" * 40, "--dry-run", "--json")
expect(p.returncode == 0 and json.loads(p.stdout)["commitVerified"] is False, "outside a work tree the commit is accepted but reported as not verified")

# nothing is sent anywhere
src = open(os.path.join(HERE, "ingest.py")).read() + open(os.path.join(HERE, "check_submission.py")).read()
expect(not re.search(r"^\s*(import|from)\s+(socket|urllib|http|requests|ftplib|smtplib|ssl|boto3|paramiko)\b", src, re.M), "ingest.py and check_submission.py import no network module")

if FAILS:
    print("test_submission: FAIL (%d)" % len(FAILS))
    sys.exit(1)
print("test_submission: all checks behaved as expected")
