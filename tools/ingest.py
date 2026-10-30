#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Turn an accepted (merged) delivery into isolated, content-addressed component assets and a neutral catalogue.

    python3 tools/ingest.py deliveries/SLUG --commit FULL_COMMIT_HASH --out OUT_DIR [--dry-run] [--json]
                            [--profile PROFILE.json] [--require-ancestor-of REF] [--max-seconds N] [--max-memory-mb N]

Acceptance of a submission is a merge to the main branch, so run this on a checkout of the merged commit, never on a contributor
branch. `--commit` names that commit; when DELIVERY is inside a git work tree the tool also requires HEAD to equal it and the
delivery folder to be unchanged, and with `--require-ancestor-of origin/main` that the commit is part of that branch.

What it does, in order (any failure stops it before anything is written):
 1. copies the delivery (plain files only) into a temporary folder and re-runs check_submission.py and check_all.py on the copy;
 2. splits it into components: every furniture or fixture item under items/ and, from the master IFC, every furniture element, covering
    (wall, floor, ceiling), fixture or luminaire assembly, hardware piece, door and window; every texture set under finishes/textures/
    becomes a material set;
 3. exports each geometry component as one binary glTF (GLB) file, deterministic and verified by reading it back;
 4. stores every file by content hash as OUT_DIR/blobs/sha256/<hash>.<ext> (the same bytes from another delivery are stored once);
 5. writes OUT_DIR/catalogue/index.json, OUT_DIR/catalogue/deliveries/<slug>@<commit12>.json and the handoff manifest
    OUT_DIR/handoff/<slug>@<commit12>.json (schemas/catalogue.schema.json).
The output depends only on the delivery bytes and the commit hash: no times, no host names. Nothing is uploaded and no network is used.
With --dry-run nothing is written; the report shows what would be stored and what already exists in OUT_DIR.

GLB conventions: units are metres; the axes are converted from the IFC frame (Z up) to glTF (Y up) by (x, y, z) -> (x, z, -y).
All catalogue numbers (dimensions, bounds, pivot, anchors, placement) stay in the IFC frame. Geometry from the master IFC is moved so
that its pivot is the centre of its footprint at its lowest point; the pivot's position in the building file is recorded as the
occurrence placement. Items under items/ keep the pivot their item.json declares.

Exit codes: 0 done; 1 the checks refused the delivery; 2 wrong command line; 3 an error or a limit (time, memory, size, components).
Requires the packages of tools/requirements.txt (ifcopenshell, numpy, jsonschema).
"""
import argparse
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report as rpt  # noqa: E402
import check_submission  # noqa: E402
import glbkit  # noqa: E402
from glbkit import Failed, kind_and_category, kind_of_class, part_products, r6, rl, read_glb, sha256_bytes, slugify, write_glb  # noqa: E402,F401  (read_glb and write_glb: the tests use them from here)

VERSION = "2.5.0"
ROOT = rpt.ROOT

MEDIA = {"glb": "model/gltf-binary", "ifc": "application/x-step", "png": "image/png", "jpg": "image/jpeg", "json": "application/json"}


class Refused(Exception):
    """The checks or the form of the delivery do not allow ingest (exit 1)."""


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=True) + "\n").encode("ascii")


# ---------------------------------------------------------------- limits
class Limits:
    def __init__(self, seconds, memory_mb):
        self.deadline = time.monotonic() + seconds
        self.seconds = seconds
        if hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, self._alarm)
            signal.alarm(max(1, int(seconds) + 5))             # hard stop even inside a native call
        if memory_mb:
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (memory_mb << 20, memory_mb << 20))
            except (ImportError, ValueError, OSError):
                pass

    def _alarm(self, *_):
        raise Failed("time limit of %d seconds exceeded" % self.seconds)

    def left(self):
        return self.deadline - time.monotonic()

    def tick(self):
        if self.left() <= 0:
            raise Failed("time limit of %d seconds exceeded" % self.seconds)


# ---------------------------------------------------------------- git provenance
def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)


def check_commit(delivery, commit, ancestor_of):
    """Verify the commit against the work tree the delivery is in. Returns True when it was verified, False when there is no work tree."""
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit or ""):
        raise Refused("--commit must be the full lower-case commit hash (40 or 64 hexadecimal characters)")
    try:
        top = git(["rev-parse", "--show-toplevel"], delivery)
    except (OSError, subprocess.SubprocessError):
        top = None
    if top is None or top.returncode:
        if ancestor_of:
            raise Refused("--require-ancestor-of needs the delivery to be inside a git work tree")
        return False
    head = git(["rev-parse", "HEAD"], delivery).stdout.strip()
    if head != commit:
        raise Refused("HEAD is %s but --commit is %s: check out the merged commit first" % (head[:12], commit[:12]))
    dirty = git(["status", "--porcelain", "--untracked-files=all", "--", "."], delivery).stdout.strip()
    if dirty:
        raise Refused("the delivery folder differs from the commit (uncommitted or untracked files); ingest only committed content")
    if ancestor_of:
        r = git(["merge-base", "--is-ancestor", commit, ancestor_of], delivery)
        if r.returncode:
            raise Refused("commit %s is not part of %s: only merged commits are ingested" % (commit[:12], ancestor_of))
    return True


# ---------------------------------------------------------------- the checks
def run_checks(copy, profile_path, limits):
    """Re-run the checks on the copy. Returns the list of {profile, result, requiredFailures, recommendedWarnings}."""
    rpt.load_profile(profile_path)
    form = check_submission.check(copy)
    results = [{"profile": rpt.profile_info()["name"], "tool": "check_submission.py", "result": form["result"],
                "requiredFailures": form["summary"]["requiredFailures"]}]
    if form["summary"]["requiredFailures"]:
        raise Refused("check_submission.py: " + next(f["message"] for f in form["findings"] if f["status"] == "fail"))
    with open(os.path.join(copy, "delivery.json"), encoding="utf-8") as fh:
        wanted = ((json.load(fh).get("submission") or {}).get("profile") or {}).get("name")
    profiles = [profile_path]
    named = os.path.join(ROOT, "profiles", "%s.json" % wanted) if wanted and re.fullmatch(r"[a-z0-9][a-z0-9._-]*", wanted) else None
    if named and os.path.exists(named) and os.path.abspath(named) not in [os.path.abspath(p) for p in profiles if p]:
        profiles.append(named)
    for pr in profiles:
        cmd = [sys.executable, os.path.join(HERE, "check_all.py"), copy, "--json"] + (["--profile", pr] if pr else [])
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=max(5, limits.left()))
        try:
            rep = json.loads(p.stdout)
        except ValueError:
            raise Failed("check_all.py printed no report (exit %d)" % p.returncode)
        results.append({"profile": rep["profile"]["name"], "tool": "check_all.py", "result": rep["result"],
                        "requiredFailures": rep["summary"]["requiredFailures"], "recommendedWarnings": rep["summary"]["recommendedWarnings"]})
        if p.returncode or rep["summary"]["requiredFailures"]:
            bad = next((f for f in rep["findings"] if f["status"] == "fail"), None)
            if bad is None:
                raise Failed("check_all.py under profile %s could not finish: %s" % (rep["profile"]["name"], str(rep.get("error", "error"))[:200]))
            raise Refused("check_all.py under profile %s: %s" % (rep["profile"]["name"], "%s %s" % (bad["rule"], bad["message"])))
    return results


def hexcol(c):
    return "#%02x%02x%02x" % tuple(int(round(x * 255)) for x in c[:3])


# ---------------------------------------------------------------- component building
class Store:
    """Content-addressed blobs: staged in memory, written on commit."""

    def __init__(self, out):
        self.out = out
        self.new, self.existing = {}, {}          # sha -> (ext, bytes)

    def put(self, data, ext):
        h = sha256_bytes(data)
        rel = "blobs/sha256/%s.%s" % (h, ext)
        if h in self.new or h in self.existing:
            return rel, h
        path = os.path.join(self.out, rel) if self.out else None
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                if sha256_bytes(fh.read()) != h:
                    raise Failed("the stored blob %s does not match its name" % rel)
            self.existing[h] = (ext, len(data))
        else:
            self.new[h] = (ext, data)
        return rel, h

    def commit(self):
        for h, (ext, data) in sorted(self.new.items()):
            path = os.path.join(self.out, "blobs", "sha256", "%s.%s" % (h, ext))
            atomic_write(path, data)


def atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def file_entry(store, role, rel_or_data, ext, name_for_media=None):
    data = rel_or_data
    blob, h = store.put(data, ext)
    return {"role": role, "blob": blob, "sha256": h, "bytes": len(data), "mediaType": MEDIA.get(ext, "application/octet-stream")}


def psets_of(e):
    import ifcopenshell.util.element as ue
    out = {}
    try:
        ps = ue.get_psets(e, psets_only=True)
    except Exception:
        return out
    n = 0
    for pn in sorted(ps):
        props = {}
        for k in sorted(ps[pn]):
            if k == "id" or n >= 100:
                continue
            v = ps[pn][k]
            if isinstance(v, bool) or isinstance(v, int):
                props[k] = v
            elif isinstance(v, float):
                props[k] = r6(v) if math.isfinite(v) else None
            elif isinstance(v, str):
                props[k] = v[:300]
            else:
                continue
            n += 1
        if props:
            out[pn[:80]] = props
    return out


def material_refs(parts_cols, cls_list, schedule, set_ids):
    """Link each surface colour to the finish schedule's texture sets (and to the material-set components of this delivery)."""
    refs = []
    for c in parts_cols:
        col, op = hexcol(c), round(c[3], 2)
        sets = set()
        sched = []
        for m in (schedule or {}).get("materials", []):
            k = m.get("key", {})
            if k.get("colour", "").lower() == col and round(float(k.get("opacity", 1.0)), 2) == op and k.get("class") in cls_list:
                sched.append(m.get("role", ""))
                for f in (m.get("faces") or {}).values():
                    if isinstance(f, dict) and f.get("set"):
                        sets.add(f["set"])
        refs.append({"colour": col, "opacity": op, "finishRoles": sorted(set(sched)),
                     "sets": [{"name": s, "component": set_ids.get(s)} for s in sorted(sets)]})
    return refs


def make_material_sets(copy, store, occ_base, limits):
    comps, ids = [], {}
    base = os.path.join(copy, "finishes", "textures")
    if not os.path.isdir(base):
        return comps, ids
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if not os.path.isdir(d):
            continue
        limits.tick()
        with open(os.path.join(d, "set.json"), "rb") as fh:
            setdata = fh.read()
        sj = json.loads(setdata.decode("utf-8"))
        files, maps = [], {}
        for mapname, fn in sorted((sj.get("maps") or {}).items()):
            with open(os.path.join(d, fn), "rb") as fh:
                data = fh.read()
            e = file_entry(store, "map-" + slugify(mapname), data, "png")
            files.append(e)
            maps[mapname] = e["sha256"]
        files.append(file_entry(store, "set-description", setdata, "json"))
        desc = {"format": "material-set/1", "name": name, "version": sj.get("version"), "tileMetres": sj.get("tileMetres"),
                "sizePixels": sj.get("sizePixels"), "tintMode": sj.get("tintMode"), "maps": maps, "setDescription": files[-1]["sha256"]}
        dfile = file_entry(store, "descriptor", canonical(desc), "json")
        cid = "sha256:" + dfile["sha256"]
        ids[name] = cid
        comps.append({"id": cid, "kind": "material-set", "category": "material-set", "name": name,
                      "files": [dfile] + files,
                      "material": {"tileMetres": sj.get("tileMetres"), "sizePixels": sj.get("sizePixels"), "tintMode": sj.get("tintMode"),
                                   "direction": sj.get("direction"), "maps": sorted(maps)},
                      "occurrence": dict(occ_base, name=name, sourcePath="finishes/textures/" + name)})
    return comps, ids


def make_geometry_component(store, root, model, copy_rel, limits, occ_base, schedule, set_ids, recentre, item=None, extra_files=()):
    import numpy as np
    geo = glbkit.component_geometry(model, root, limits, recentre)
    parts, m_root, lo, hi, shift, ntri, glb, info = (geo[k] for k in ("parts", "m_root", "lo", "hi", "shift", "triangles", "glb", "info"))
    gfile = file_entry(store, "geometry", glb, "glb")
    kind, cat = (item["kind"], item["category"]) if item else kind_and_category(root, part_products(root))
    world = m_root @ np.array([shift[0], shift[1], shift[2], 1.0])
    rot = math.degrees(math.atan2(m_root[1, 0], m_root[0, 0]))
    dims = hi - lo
    classes = sorted({p.is_a() for p in part_products(root)})
    comp = {"id": "sha256:" + gfile["sha256"], "kind": kind, "category": cat, "name": str(root.Name or cat)[:120],
            "files": [gfile] + list(extra_files),
            "geometry": {"format": "glb", "units": "metres", "glbAxes": "y-up", "frame": "ifc-z-up",
                         "bounds": {"min": rl(lo), "max": rl(hi)}, "dimensions": {"x": r6(dims[0]), "y": r6(dims[1]), "z": r6(dims[2])},
                         "pivot": {"kind": "footprint-centre-at-lowest-point" if recentre else "as-authored",
                                   "position": [0.0, 0.0, 0.0]},
                         "triangles": ntri, "primitives": info["primitives"]},
            "anchors": [{"id": "pivot", "kind": "origin", "position": [0.0, 0.0, 0.0], "direction": [0, 0, 1]}],
            "materialRefs": material_refs([c for c, _ in parts], classes, schedule, set_ids),
            "occurrence": dict(occ_base, name=str(root.Name or cat)[:120], sourcePath=copy_rel, sourceId=root.GlobalId,
                               ifcClass=root.is_a(), placement={"frame": "building-file", "position": rl(world[:3]), "rotationZDegrees": round(rot, 4)},
                               properties=psets_of(root))}
    if item:
        comp["anchors"] += item.get("anchors", [])
        comp["occurrence"]["item"] = item["meta"]
    return comp


def master_components(copy, man, store, limits, occ_base, schedule, set_ids):
    import ifcopenshell
    out = []
    ifcs = [f["path"] for f in man["files"] if f["role"] == "master-ifc"]
    for rel in ifcs:
        limits.tick()
        model = ifcopenshell.open(os.path.join(copy, rel))
        for root, _parts, _kind, _cat in glbkit.master_roots(model):
            limits.tick()
            out.append(make_geometry_component(store, root, model, rel, limits, occ_base, schedule, set_ids, True))
            if len(out) > rpt.param("submission.ingestMaxComponents", 500):
                raise Failed("more than %d components" % rpt.param("submission.ingestMaxComponents", 500))
    return out


def item_components(copy, store, limits, occ_base, schedule, set_ids):
    import ifcopenshell
    out = []
    base = os.path.join(copy, "items")
    if not os.path.isdir(base):
        return out
    for iid in sorted(os.listdir(base)):
        d = os.path.join(base, iid)
        if not os.path.isdir(d):
            continue
        limits.tick()
        ifc_rel, js_rel = "items/%s/%s.ifc" % (iid, iid), "items/%s/%s.item.json" % (iid, iid)
        with open(os.path.join(copy, js_rel), "rb") as fh:
            jdata = fh.read()
        jd = json.loads(jdata.decode("utf-8"))
        with open(os.path.join(copy, ifc_rel), "rb") as fh:
            idata = fh.read()
        model = ifcopenshell.open(os.path.join(copy, ifc_rel))
        root = glbkit.item_root(model, ifc_rel)
        kind = kind_of_class(jd.get("class", "")) or kind_of_class(root.is_a()) or "furniture"
        extra = [file_entry(store, "source-ifc", idata, "ifc"), file_entry(store, "description", jdata, "json")]
        prev = os.path.join(d, "preview.png")
        if os.path.exists(prev):
            with open(prev, "rb") as fh:
                extra.append(file_entry(store, "preview", fh.read(), "png"))
        meta = {k: jd[k] for k in ("itemId", "version", "class", "front", "footprint", "collision", "clearance", "placement", "variants", "budget") if k in jd}
        item = {"kind": kind, "category": slugify(jd.get("category"), "item"), "anchors": jd.get("anchors", []), "meta": meta}
        comp = make_geometry_component(store, root, model, ifc_rel, limits, occ_base, schedule, set_ids, False, item=item, extra_files=extra)
        comp["name"] = str(jd.get("name") or root.Name)[:120]
        comp["occurrence"]["name"] = comp["name"]
        comp["geometry"]["pivot"].update({k: v for k, v in (jd.get("pivot") or {}).items() if k in ("kind", "description")})
        comp["geometry"]["pivot"]["kind"] = str((jd.get("pivot") or {}).get("kind", "as-authored"))
        comp["geometry"]["declaredDimensions"] = jd.get("dimensions")
        out.append(comp)
    return out


# ---------------------------------------------------------------- proofs (rule X-79 to X-86)
def proof_records(copy, comps, store, limits):
    """Compare the contributor's proofs with a fresh export from the delivered files, and link the renders to the components.

    The ingest result stays authoritative: nothing here changes a component or refuses a delivery; a mismatch is reported (and the
    reproducibility check, check_proofs.py --reproduce, is what a pull request is held to). Returns None when the delivery has no proofs."""
    mp = os.path.join(copy, "proofs", "manifest.json")
    if not os.path.exists(mp):
        return None
    with open(mp, encoding="utf-8") as fh:
        pm = json.load(fh)
    cmp = {"glbMatched": 0, "glbMismatched": [], "glbMissingFromProofs": [], "glbNotInDelivery": [], "rendersChecked": 0, "rendersMismatched": [],
           "ingestGlbNotInProofs": []}
    try:
        import export_glb
        now = {"proofs/glb/" + e["rel"]: e["sha256"] for g in export_glb.export_delivery(copy, limits).values() for e in g}
    except Exception as exc:
        cmp["error"] = "re-export failed: %s" % str(exc)[:160]
        now = {}
    stored = {g["path"]: g["sha256"] for g in pm.get("glb", [])}
    for path, sha in sorted(now.items()):
        if path not in stored:
            cmp["glbMissingFromProofs"].append(path)
        elif stored[path] == sha:
            cmp["glbMatched"] += 1
        else:
            cmp["glbMismatched"].append(path)
    if now:
        cmp["glbNotInDelivery"] = sorted(set(stored) - set(now))
    have = set(stored.values())
    cmp["ingestGlbNotInProofs"] = sorted({c["files"][0]["sha256"][:12] for c in comps if c["kind"] != "material-set" and c["files"][0]["sha256"] not in have})
    sheets = {}
    for r in pm.get("renders", []):
        with open(os.path.join(copy, r["path"]), "rb") as fh:
            data = fh.read()
        cmp["rendersChecked"] += 1
        if sha256_bytes(data) != r["sha256"]:
            cmp["rendersMismatched"].append(r["path"])
            continue
        if r["kind"] == "sheet":
            sheets[r["glbSha256"]] = data
    by_key = {k: g["sha256"] for g in pm.get("glb", []) for k in g["keys"]}
    for c in comps:
        sha = by_key.get("material:" + c["name"]) if c["kind"] == "material-set" else c["files"][0]["sha256"]
        if sha in sheets:
            c["files"].append(file_entry(store, "proof-render", sheets[sha], "png"))
    rec = {"manifest": {"sha256": sha256_bytes(open(mp, "rb").read())}, "compare": cmp, "renders": [], "glb": []}
    for r in pm.get("renders", []):
        if r["path"] in cmp["rendersMismatched"]:
            continue
        with open(os.path.join(copy, r["path"]), "rb") as fh:
            blob = store.put(fh.read(), "png")[0]
        rec["renders"].append({"path": r["path"], "sha256": r["sha256"], "bytes": r["bytes"], "blob": blob, "kind": r["kind"], "subject": r["subject"],
                               "glbSha256": r["glbSha256"], "width": r["width"], "height": r["height"]})
    for g in pm.get("glb", []):
        row = {"path": g["path"], "sha256": g["sha256"], "bytes": g["bytes"], "role": g["role"], "keys": g["keys"]}
        if g["role"] == "model":
            with open(os.path.join(copy, g["path"]), "rb") as fh:
                row["blob"] = store.put(fh.read(), "glb")[0]
        rec["glb"].append(row)
    return rec


# ---------------------------------------------------------------- catalogue
def load_index(out):
    p = os.path.join(out, "catalogue", "index.json") if out else None
    if p and os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            idx = json.load(fh)
        if idx.get("format") != "catalogue-index/1":
            raise Failed("%s is not a catalogue-index/1 file" % p)
        return idx
    return {"format": "catalogue-index/1", "generator": {"tool": "ingest.py", "version": VERSION}, "components": [], "deliveries": []}


def merge_index(idx, comps, drec):
    by = {c["id"]: c for c in idx["components"]}
    dedup = []                                   # per component, in order: was its content already in the catalogue (or earlier in this delivery)
    for c in comps:
        occ = c["occurrence"]
        if c["id"] in by:
            cur = by[c["id"]]
            have = {(o["delivery"], o["commit"], o["sourcePath"], o.get("sourceId")) for o in cur["occurrences"]}
            key = (occ["delivery"], occ["commit"], occ["sourcePath"], occ.get("sourceId"))
            if key not in have:
                cur["occurrences"].append(occ)
                cur["occurrences"].sort(key=lambda o: (o["delivery"], o["commit"], o["sourcePath"], o.get("sourceId") or ""))
            known = {f["sha256"] for f in cur["files"]}
            cur["files"] += [f for f in c["files"] if f["sha256"] not in known]
            dedup.append(True)
        else:
            dedup.append(False)
            n = {k: v for k, v in c.items() if k != "occurrence"}
            n["occurrences"] = [occ]
            by[c["id"]] = n
    idx["components"] = [by[k] for k in sorted(by)]
    idx["deliveries"] = sorted([d for d in idx["deliveries"] if (d["delivery"], d["commit"]) != (drec["delivery"]["slug"], drec["delivery"]["commit"])]
                               + [{"delivery": drec["delivery"]["slug"], "commit": drec["delivery"]["commit"], "record": drec["_path"],
                                   "components": drec["componentIds"]}], key=lambda d: (d["delivery"], d["commit"]))
    return dedup


# ---------------------------------------------------------------- main flow
def ingest(delivery, commit, out, dry, profile_path, ancestor_of, max_seconds, max_memory):
    delivery = os.path.abspath(delivery)
    rpt.load_profile(profile_path)
    seconds = max_seconds or rpt.param("submission.ingestMaxSeconds", 300)
    limits = Limits(seconds, max_memory)
    slug = os.path.basename(delivery)
    work = tempfile.mkdtemp(prefix="ingest-")
    try:
        verified = check_commit(delivery, commit, ancestor_of)
        # form check on the original (looks at names and modes only), then a copy of plain files
        pre = check_submission.check(delivery)
        if pre["summary"]["requiredFailures"]:
            raise Refused("check_submission.py: " + next(f["message"] for f in pre["findings"] if f["status"] == "fail"))
        copy = os.path.join(work, slug)
        for r, st in check_submission.walk(delivery):
            if stat.S_ISDIR(st.st_mode):
                os.makedirs(os.path.join(copy, r), exist_ok=True)
        os.makedirs(copy, exist_ok=True)
        for r, st in check_submission.walk(delivery):
            if stat.S_ISREG(st.st_mode):
                shutil.copyfile(os.path.join(delivery, r), os.path.join(copy, r), follow_symlinks=False)
                os.chmod(os.path.join(copy, r), 0o644)
        checks = run_checks(copy, profile_path, limits)
        with open(os.path.join(copy, "delivery.json"), encoding="utf-8") as fh:
            man = json.load(fh)
        sub = man["submission"]
        occ_base = {"delivery": slug, "commit": commit, "submitter": sub["submitter"]["handle"], "licence": sub["licence"]}
        schedule = None
        sp = os.path.join(copy, "finishes", "finish-schedule.json")
        if os.path.exists(sp):
            with open(sp, encoding="utf-8") as fh:
                schedule = json.load(fh)
        store = Store(out)
        comps, set_ids = make_material_sets(copy, store, occ_base, limits)
        comps += item_components(copy, store, limits, occ_base, schedule, set_ids)
        comps += master_components(copy, man, store, limits, occ_base, schedule, set_ids)
        if len(comps) > rpt.param("submission.ingestMaxComponents", 500):
            raise Failed("more than %d components" % rpt.param("submission.ingestMaxComponents", 500))
        if not comps:
            raise Refused("the delivery holds nothing that can be taken in as a component")
        proofs = proof_records(copy, comps, store, limits)
        # the source files themselves, by hash, so the record can point at exactly what was merged
        sources = []
        for f in sorted(man["files"], key=lambda f: f["path"]):
            ext = f["path"].rsplit(".", 1)[-1].lower()
            e = {"path": f["path"], "role": f["role"], "sha256": f["sha256"], "bytes": f["bytes"]}
            if f["role"] in ("master-ifc", "alternate-ifc", "item-ifc", "item-preview", "proof-render") and ext in ("ifc", "png", "jpg"):
                with open(os.path.join(copy, f["path"]), "rb") as fh:
                    e["blob"] = store.put(fh.read(), ext)[0]
            sources.append(e)
        for p in ("delivery.json",):
            with open(os.path.join(copy, p), "rb") as fh:
                data = fh.read()
            sources.append({"path": p, "role": "delivery-manifest", "sha256": sha256_bytes(data), "bytes": len(data), "blob": store.put(data, "json")[0]})
        tag = "%s@%s" % (slug, commit[:12])
        drec = {"format": "catalogue-delivery/1",
                "delivery": {"slug": slug, "id": man["delivery"]["id"], "version": man["delivery"]["version"], "title": sub["title"],
                             "commit": commit, "commitVerified": verified, "submitter": sub["submitter"]["handle"], "licence": sub["licence"],
                             "kinds": man["delivery"]["kind"], "profile": sub["profile"], "toolVersions": sub["toolVersions"]},
                "checks": checks, "sources": sources, "componentIds": sorted({c["id"] for c in comps}),
                "components": [{"id": c["id"], "kind": c["kind"], "category": c["category"], "name": c["name"], "sourcePath": c["occurrence"]["sourcePath"]}
                               for c in sorted(comps, key=lambda c: (c["occurrence"]["sourcePath"], c["occurrence"].get("sourceId") or "", c["id"]))],
                "generator": {"tool": "ingest.py", "version": VERSION}}
        if proofs:
            drec["proofs"] = proofs
        drec["_path"] = "catalogue/deliveries/%s.json" % tag
        idx = load_index(out)
        dedup = merge_index(idx, comps, drec)
        for c, d in zip(comps, dedup):
            c["duplicate"] = d
        rec_path = drec.pop("_path")
        rec_bytes = canonical(drec)
        idx_bytes = canonical(idx)
        added = sorted(({"blob": "blobs/sha256/%s.%s" % (h, ext), "sha256": h, "bytes": len(d)} for h, (ext, d) in store.new.items()), key=lambda x: x["blob"])
        existing = sorted(({"blob": "blobs/sha256/%s.%s" % (h, ext), "sha256": h, "bytes": n} for h, (ext, n) in store.existing.items()), key=lambda x: x["blob"])
        hand = {"format": "ingest-handoff/1", "delivery": drec["delivery"],
                "blobsToPublish": added, "blobsAlreadyPresent": existing,
                "components": [{"id": c["id"], "kind": c["kind"], "category": c["category"], "name": c["name"],
                                "files": [{"role": f["role"], "blob": f["blob"], "sha256": f["sha256"], "bytes": f["bytes"], "mediaType": f["mediaType"]} for f in c["files"]],
                                "licence": sub["licence"], "submitter": sub["submitter"]["handle"], "commit": commit,
                                "alreadyInCatalogue": c["duplicate"]} for c in sorted(comps, key=lambda c: (c["id"], c["duplicate"], c["occurrence"]["sourcePath"], c["occurrence"].get("sourceId") or ""))],
                "catalogue": {"index": "catalogue/index.json", "indexSha256": sha256_bytes(idx_bytes), "record": rec_path, "recordSha256": sha256_bytes(rec_bytes)},
                "counts": {"components": len(comps), "uniqueComponents": len(drec["componentIds"]), "blobsNew": len(added), "blobsExisting": len(existing),
                           "bytesNew": sum(a["bytes"] for a in added)},
                "uploaded": False, "generator": {"tool": "ingest.py", "version": VERSION}}
        hand_path = "handoff/%s.json" % tag
        if not dry:
            store.commit()
            atomic_write(os.path.join(out, rec_path), rec_bytes)
            atomic_write(os.path.join(out, "catalogue", "index.json"), idx_bytes)
            if not os.path.exists(os.path.join(out, hand_path)):      # the first handoff of a commit is kept: it lists what was new then
                atomic_write(os.path.join(out, hand_path), canonical(hand))
        return {"dryRun": dry, "handoff": hand_path, "record": rec_path, "summary": hand["counts"], "components": hand["components"],
                "blobsToPublish": added, "blobsAlreadyPresent": existing, "checks": checks, "commitVerified": verified,
                "handoffSha256": sha256_bytes(canonical(hand)), "proofs": (proofs or {}).get("compare")}
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("delivery", help="deliveries/SLUG in a checkout of the merged commit")
    ap.add_argument("--commit", required=True, help="full hash of the merged commit (provenance)")
    ap.add_argument("--out", help="output folder (required unless --dry-run); an existing catalogue there is extended")
    ap.add_argument("--dry-run", action="store_true", help="do everything except writing; compare with --out when given")
    ap.add_argument("--profile")
    ap.add_argument("--require-ancestor-of", metavar="REF", help="refuse unless the commit is part of this ref, for example origin/main")
    ap.add_argument("--max-seconds", type=int, default=0)
    ap.add_argument("--max-memory-mb", type=int, default=0, help="address-space limit; 0 = none")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not a.dry_run and not a.out:
        ap.error("--out is required unless --dry-run")
    if not os.path.isdir(a.delivery) or os.path.islink(a.delivery):
        print("ERROR not a folder: %s" % a.delivery, file=sys.stderr)
        sys.exit(3)
    try:
        res = ingest(a.delivery, a.commit, os.path.abspath(a.out) if a.out else None, a.dry_run, a.profile, a.require_ancestor_of, a.max_seconds, a.max_memory_mb)
    except Refused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        sys.exit(1)
    except Failed as exc:
        print("FAILED: %s" % exc, file=sys.stderr)
        sys.exit(3)
    except MemoryError:
        print("FAILED: memory limit exceeded", file=sys.stderr)
        sys.exit(3)
    if a.json:
        print(json.dumps(res, indent=1, sort_keys=True))
    else:
        s = res["summary"]
        print("%s: %d component(s) (%d unique), %d new blob(s) (%d bytes), %d already stored%s" % (
            "dry run" if res["dryRun"] else "ingested", s["components"], s["uniqueComponents"], s["blobsNew"], s["bytesNew"], s["blobsExisting"],
            "" if res["commitVerified"] else "; commit not verified against a work tree"))
        pc = res.get("proofs")
        if pc is not None:
            bad = len(pc["glbMismatched"]) + len(pc["glbMissingFromProofs"]) + len(pc["glbNotInDelivery"]) + len(pc["rendersMismatched"]) + len(pc["ingestGlbNotInProofs"])
            print("proofs: %d GLB file(s) match a fresh export, %d render(s) checked%s" % (pc["glbMatched"], pc["rendersChecked"], "" if not bad and "error" not in pc else
                  "; MISMATCH: %s" % json.dumps({k: v for k, v in pc.items() if v and k not in ("glbMatched", "rendersChecked")})[:300]))
        else:
            print("proofs: none in the delivery")
        for c in res["components"]:
            print("  %-12s %-16s %s  %s%s" % (c["kind"], c["category"], c["id"][:19], c["name"], "  (already in catalogue)" if c["alreadyInCatalogue"] else ""))
        if not res["dryRun"]:
            print("handoff manifest: %s" % res["handoff"])


if __name__ == "__main__":
    main()
