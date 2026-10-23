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
import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report as rpt  # noqa: E402
import check_submission  # noqa: E402

VERSION = "2.2.0"
ROOT = rpt.ROOT
MAX_TRIANGLES = 2000000          # per component
MEDIA = {"glb": "model/gltf-binary", "ifc": "application/x-step", "png": "image/png", "jpg": "image/jpeg", "json": "application/json"}
FURNITURE = {"IfcFurnishingElement", "IfcFurniture", "IfcSystemFurnitureElement"}
FIXTURE = {"IfcLightFixture", "IfcLamp", "IfcSanitaryTerminal", "IfcElectricAppliance", "IfcFlowTerminal", "IfcAlarm", "IfcOutlet",
           "IfcSwitchingDevice", "IfcAudioVisualAppliance", "IfcCommunicationsAppliance", "IfcSensor", "IfcWasteTerminal"}
HARDWARE = {"IfcDiscreteAccessory", "IfcMechanicalFastener", "IfcFastener", "IfcRailing"}
KIND_OF = {"IfcCovering": "covering", "IfcDoor": "door", "IfcWindow": "window"}
COVERING_CATEGORY = {"FLOORING": "floor-covering", "CEILING": "ceiling-covering", "CLADDING": "wall-covering", "WRAPPING": "wall-covering",
                     "MEMBRANE": "covering", "INSULATION": "covering", "SLEEVING": "covering", "MOLDING": "covering", "SKIRTINGBOARD": "covering"}
SKIP_CLASSES = {"IfcOpeningElement", "IfcVirtualElement", "IfcSpace", "IfcAnnotation", "IfcGrid", "IfcGeographicElement"}


class Refused(Exception):
    """The checks or the form of the delivery do not allow ingest (exit 1)."""


class Failed(Exception):
    """A limit, a read error or an internal check failed (exit 3)."""


def slugify(text, default="item"):
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s[:60] or default


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=True) + "\n").encode("ascii")


def r6(x):
    v = round(float(x), 6)
    return 0.0 if v == 0 else v


def rl(seq):
    return [r6(x) for x in seq]


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


# ---------------------------------------------------------------- GLB
def write_glb(parts):
    """parts: list of (rgba tuple, Nx3 float array of triangle-soup vertices, Z up). Returns the GLB bytes."""
    import numpy as np
    bin_chunks, views, accs, prims, mats = [], [], [], [], []
    off = 0
    for rgba, tri in sorted(parts, key=lambda p: tuple(p[0])):
        v = np.array(tri, dtype=np.float64).reshape(-1, 3)
        v = np.stack([v[:, 0], v[:, 2], -v[:, 1]], axis=1)                  # Z up -> Y up
        t = v.reshape(-1, 3, 3)
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
        ln = np.linalg.norm(n, axis=1)
        n = n / np.where(ln > 1e-12, ln, 1.0)[:, None]
        nv = np.repeat(n, 3, axis=0).astype("<f4")
        pv = v.astype("<f4")
        for arr, tgt in ((pv, 34962), (nv, 34962)):
            b = arr.tobytes()
            views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b), "target": tgt})
            bin_chunks.append(b)
            off += len(b)
        accs.append({"bufferView": len(views) - 2, "componentType": 5126, "count": int(len(pv)), "type": "VEC3",
                     "min": [float(x) for x in pv.min(axis=0)], "max": [float(x) for x in pv.max(axis=0)]})
        accs.append({"bufferView": len(views) - 1, "componentType": 5126, "count": int(len(nv)), "type": "VEC3"})
        mats.append({"pbrMetallicRoughness": {"baseColorFactor": [float(x) for x in rgba], "metallicFactor": 0.0, "roughnessFactor": 0.9},
                     "alphaMode": "BLEND" if rgba[3] < 0.999 else "OPAQUE", "doubleSided": True})
        prims.append({"attributes": {"POSITION": len(accs) - 2, "NORMAL": len(accs) - 1}, "material": len(mats) - 1, "mode": 4})
    doc = {"asset": {"version": "2.0", "generator": "authoring-guide-set ingest " + VERSION},
           "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}], "meshes": [{"primitives": prims}],
           "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": off}],
           "extras": {"units": "metres", "axisConversion": "(x,y,z) -> (x,z,-y) from the IFC frame (Z up) to glTF (Y up)"}}
    js = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("ascii")
    js += b" " * (-len(js) % 4)
    bn = b"".join(bin_chunks)
    bn += b"\0" * (-len(bn) % 4)
    total = 12 + 8 + len(js) + 8 + len(bn)
    return b"glTF" + struct.pack("<II", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(bn), b"BIN\0") + bn


def read_glb(data):
    """Parse and validate a GLB written by write_glb (also any plain triangle GLB). Returns {'triangles', 'min', 'max', 'primitives'} in glTF axes."""
    import numpy as np
    if len(data) < 28 or data[:4] != b"glTF":
        raise Failed("not a GLB file")
    ver, total = struct.unpack("<II", data[4:12])
    if ver != 2 or total != len(data):
        raise Failed("GLB header: version %d, length %d of %d" % (ver, total, len(data)))
    jl, jt = struct.unpack("<I4s", data[12:20])
    if jt != b"JSON" or 20 + jl + 8 > len(data):
        raise Failed("GLB has no JSON chunk")
    doc = json.loads(data[20:20 + jl].decode("ascii"))
    bl, bt = struct.unpack("<I4s", data[20 + jl:28 + jl])
    if bt != b"BIN\0" or 28 + jl + bl != len(data):
        raise Failed("GLB has no BIN chunk of the stated length")
    bn = data[28 + jl:28 + jl + bl]
    if doc["buffers"][0]["byteLength"] > len(bn):
        raise Failed("GLB buffer is shorter than declared")
    tris, lo, hi = 0, None, None
    for pr in doc["meshes"][0]["primitives"]:
        acc = doc["accessors"][pr["attributes"]["POSITION"]]
        bv = doc["bufferViews"][acc["bufferView"]]
        if acc["componentType"] != 5126 or acc["type"] != "VEC3" or bv["byteOffset"] + acc["count"] * 12 > bl or acc["count"] % 3:
            raise Failed("GLB position accessor is malformed")
        arr = np.frombuffer(bn, dtype="<f4", count=acc["count"] * 3, offset=bv["byteOffset"]).reshape(-1, 3)
        if not np.isfinite(arr).all():
            raise Failed("GLB holds a non-finite coordinate")
        if not (np.allclose(arr.min(axis=0), acc["min"]) and np.allclose(arr.max(axis=0), acc["max"])):
            raise Failed("GLB accessor bounds differ from the data")
        nacc = doc["accessors"][pr["attributes"]["NORMAL"]]
        if nacc["count"] != acc["count"]:
            raise Failed("GLB normals and positions differ in number")
        tris += acc["count"] // 3
        lo = arr.min(axis=0) if lo is None else np.minimum(lo, arr.min(axis=0))
        hi = arr.max(axis=0) if hi is None else np.maximum(hi, arr.max(axis=0))
    return {"triangles": tris, "min": [float(x) for x in lo], "max": [float(x) for x in hi], "primitives": len(doc["meshes"][0]["primitives"])}


# ---------------------------------------------------------------- IFC geometry
def part_products(root):
    """The geometry-carrying products of a component root: the root itself, or all parts of an assembly (recursively)."""
    out = []

    def walk(e):
        if getattr(e, "Representation", None) and not e.is_a("IfcElementAssembly") and e.is_a() not in SKIP_CLASSES:
            out.append(e)
        for rel in getattr(e, "IsDecomposedBy", None) or []:
            for c in rel.RelatedObjects:
                walk(c)
    walk(root)
    return out


def shape_parts(model, root, limits):
    """[(rgba, triangle soup Nx3 in the root's own frame)] for a component root, and the root's world matrix (4x4)."""
    import numpy as np
    import ifcopenshell.geom
    import ifcopenshell.util.placement as pl
    settings = ifcopenshell.geom.settings()
    m_root = pl.get_local_placement(root.ObjectPlacement) if root.ObjectPlacement else np.eye(4)
    inv = np.linalg.inv(m_root)
    groups = {}
    ntri = 0
    for p in part_products(root):
        limits.tick()
        try:
            sh = ifcopenshell.geom.create_shape(settings, p)
        except Exception as exc:
            raise Failed("%s %s (%s): geometry could not be built: %s" % (p.is_a(), p.Name, p.GlobalId, str(exc)[:120]))
        g = sh.geometry
        v = np.array(g.verts, dtype=float).reshape(-1, 3)
        f = np.array(g.faces, dtype=int).reshape(-1, 3)
        if not len(f):
            raise Failed("%s %s (%s) has no triangles" % (p.is_a(), p.Name, p.GlobalId))
        m_part = pl.get_local_placement(p.ObjectPlacement) if p.ObjectPlacement else np.eye(4)
        m = inv @ m_part
        v = v @ m[:3, :3].T + m[:3, 3]
        mid = np.array(g.material_ids, dtype=int)
        cols = []
        for mt in g.materials:
            try:
                c = mt.diffuse.components if hasattr(mt.diffuse, "components") else mt.diffuse
                cols.append((r6(min(1.0, max(0.0, c[0]))), r6(min(1.0, max(0.0, c[1]))), r6(min(1.0, max(0.0, c[2]))),
                             r6(1.0 - float(mt.transparency or 0.0))))
            except Exception:
                cols.append((0.8, 0.8, 0.8, 1.0))
        for i in range(len(f)):
            col = cols[mid[i]] if 0 <= mid[i] < len(cols) else (0.8, 0.8, 0.8, 1.0)
            groups.setdefault(col, []).append(v[f[i]])
        ntri += len(f)
        if ntri > MAX_TRIANGLES:
            raise Failed("component %s has more than %d triangles" % (root.Name, MAX_TRIANGLES))
    return [(c, np.array(t, dtype=float).reshape(-1, 3)) for c, t in sorted(groups.items())], m_root


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


def bounds_info(parts, recentre):
    import numpy as np
    allv = np.concatenate([t for _, t in parts])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    shift = np.zeros(3)
    if recentre:
        shift = np.array([(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, lo[2]])
    return lo, hi, shift


def kind_and_category(e, parts):
    cls = e.is_a()
    ot = slugify(getattr(e, "ObjectType", None), "")
    if cls == "IfcElementAssembly":
        kinds = {kind_of_class(p.is_a()) for p in parts}
        kinds.discard(None)
        if len(kinds) != 1:
            return None, None
        k = kinds.pop()
        return k, ot or ("luminaire" if k == "fixture" else k)
    k = kind_of_class(cls)
    if k is None:
        return None, None
    if cls == "IfcCovering":
        return k, COVERING_CATEGORY.get(str(getattr(e, "PredefinedType", "") or ""), "covering")
    return k, ot or slugify(cls[3:])


def kind_of_class(cls):
    if cls in FURNITURE:
        return "furniture"
    if cls in FIXTURE:
        return "fixture"
    if cls in HARDWARE:
        return "hardware"
    return KIND_OF.get(cls)


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
    parts, m_root = shape_parts(model, root, limits)
    lo, hi, shift = bounds_info(parts, recentre)
    parts = [(c, t - shift) for c, t in parts]
    lo, hi = lo - shift, hi - shift
    # round to the precision the GLB stores, so the same shape always gives the same bytes
    parts = [(c, np.round(t, 6) + 0.0) for c, t in parts]
    glb = write_glb([(c, t) for c, t in parts])
    info = read_glb(glb)
    ntri = sum(len(t) // 3 for _, t in parts)
    if info["triangles"] != ntri:
        raise Failed("GLB check: %d triangles written, %d expected" % (info["triangles"], ntri))
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
        seen = set()
        for e in sorted(model.by_type("IfcProduct"), key=lambda x: x.GlobalId):
            cls = e.is_a()
            if cls in SKIP_CLASSES or e.id() in seen:
                continue
            root = e
            parent = None
            for rel_ in getattr(e, "Decomposes", None) or []:
                if rel_.RelatingObject.is_a("IfcElementAssembly"):
                    parent = rel_.RelatingObject
            if parent is not None:
                continue                                    # taken as part of its assembly
            parts = part_products(root)
            if not parts:
                continue
            kind, cat = kind_and_category(root, parts)
            if not kind:
                continue
            for p in parts:
                seen.add(p.id())
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
        roots = [e for e in model.by_type("IfcProduct") if e.is_a() not in SKIP_CLASSES and getattr(e, "Representation", None)
                 and not any(r.RelatingObject.is_a("IfcElementAssembly") for r in (getattr(e, "Decomposes", None) or []))]
        if len(roots) != 1:
            raise Failed("%s must hold exactly one top-level product (found %d)" % (ifc_rel, len(roots)))
        kind = kind_of_class(jd.get("class", "")) or kind_of_class(roots[0].is_a()) or "furniture"
        extra = [file_entry(store, "source-ifc", idata, "ifc"), file_entry(store, "description", jdata, "json")]
        prev = os.path.join(d, "preview.png")
        if os.path.exists(prev):
            with open(prev, "rb") as fh:
                extra.append(file_entry(store, "preview", fh.read(), "png"))
        meta = {k: jd[k] for k in ("itemId", "version", "class", "front", "footprint", "collision", "clearance", "placement", "variants", "budget") if k in jd}
        item = {"kind": kind, "category": slugify(jd.get("category"), "item"), "anchors": jd.get("anchors", []), "meta": meta}
        comp = make_geometry_component(store, roots[0], model, ifc_rel, limits, occ_base, schedule, set_ids, False, item=item, extra_files=extra)
        comp["name"] = str(jd.get("name") or roots[0].Name)[:120]
        comp["occurrence"]["name"] = comp["name"]
        comp["geometry"]["pivot"].update({k: v for k, v in (jd.get("pivot") or {}).items() if k in ("kind", "description")})
        comp["geometry"]["pivot"]["kind"] = str((jd.get("pivot") or {}).get("kind", "as-authored"))
        comp["geometry"]["declaredDimensions"] = jd.get("dimensions")
        out.append(comp)
    return out


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
        # the source files themselves, by hash, so the record can point at exactly what was merged
        sources = []
        for f in sorted(man["files"], key=lambda f: f["path"]):
            ext = f["path"].rsplit(".", 1)[-1].lower()
            e = {"path": f["path"], "role": f["role"], "sha256": f["sha256"], "bytes": f["bytes"]}
            if f["role"] in ("master-ifc", "alternate-ifc", "item-ifc", "item-preview") and ext in ("ifc", "png", "jpg"):
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
                "handoffSha256": sha256_bytes(canonical(hand))}
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
        for c in res["components"]:
            print("  %-12s %-16s %s  %s%s" % (c["kind"], c["category"], c["id"][:19], c["name"], "  (already in catalogue)" if c["alreadyInCatalogue"] else ""))
        if not res["dryRun"]:
            print("handoff manifest: %s" % res["handoff"])


if __name__ == "__main__":
    main()
