#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build and verify a delivery package (guide 4).

    python3 build_package.py init   DIR meta.json [--manifest-name delivery.json]   write DIR/manifest.json (or the named file) and DIR/SHA256SUMS.txt
    python3 build_package.py verify DIR [--json] [--report FILE]   check layout, hashes, versions, provenance, licence

A submitted delivery (guide 4, section 8) keeps its manifest in `delivery.json`; `verify` accepts that name when there is no `manifest.json`.
`meta.json` carries the fields a person writes (see templates/package-meta.template.json); the tool adds the file
list, hashes and sizes. `verify` exits 1 when any REQUIRED rule fails.

Uses only the Python standard library (and `jsonschema` if it is installed, to validate against
schemas/manifest.schema.json).
"""
import hashlib
import json
import os
import re
import sys

import report as rpt

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MANIFEST_NAMES = ("manifest.json", "delivery.json")
SKIP = {"manifest.json", "delivery.json", "SHA256SUMS.txt"}
MAPS = {"albedo.png", "normal.png", "orm.png"}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def role_of(rel):
    parts = rel.split("/")
    name = parts[-1]
    if rel.startswith("ifc/alternates/"):
        return "alternate-ifc"
    if rel.startswith("ifc/") and name.endswith(".ifc"):
        return "master-ifc"
    if rel == "finishes/finish-schedule.json":
        return "finish-schedule"
    if rel == "finishes/library.json":
        return "material-library"
    if rel == "tables/building.json":
        return "building-metadata"
    if rel == "finishes/SOURCES.csv":
        return "sources"
    if rel.startswith("finishes/textures/"):
        return "texture-map" if name in MAPS else "texture-set-description"
    if rel.startswith("items/"):
        if name.endswith(".ifc"):
            return "item-ifc"
        if name.endswith(".item.json"):
            return "item-description"
        return "item-preview"
    if rel.startswith("proofs/"):
        return {"manifest.json": "proof-manifest"}.get(name) if rel == "proofs/manifest.json" else (
            "proof-glb" if rel.startswith("proofs/glb/") else "proof-render" if rel.startswith("proofs/renders/") else
            "proof-report" if rel.startswith("proofs/reports/") else "other")
    if rel.startswith("terrain/"):
        if name.endswith(".tif") or name.endswith(".tiff"):
            return "terrain-patch"
        if name == "site-request.json":
            return "site-request"
        return "terrain-sidecar" if name.endswith(".json") else "other"
    if rel.startswith("tables/"):
        return "table"
    if rel.startswith("reports/"):
        return "report"
    if rel.startswith("notes/"):
        return "note"
    return "other"


def scan(root):
    out = []
    for base, dirs, names in os.walk(root):
        dirs.sort()
        for n in sorted(names):
            full = os.path.join(base, n)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel in SKIP:
                continue
            out.append({"path": rel, "role": role_of(rel), "sha256": sha256_of(full), "bytes": os.path.getsize(full)})
    return out


def manifest_name(root):
    """manifest.json, or delivery.json in a submitted delivery that has no manifest.json."""
    for n in MANIFEST_NAMES:
        if os.path.exists(os.path.join(root, n)):
            return n
    return MANIFEST_NAMES[0]


def init(root, meta_path, name="manifest.json"):
    if name not in MANIFEST_NAMES:
        sys.exit("--manifest-name must be one of %s" % ", ".join(MANIFEST_NAMES))
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    files = scan(root)
    man = {"format": "delivery-manifest/1"}
    man.update(meta)
    man["files"] = files
    with open(os.path.join(root, name), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(man, fh, indent=2, ensure_ascii=True)
        fh.write("\n")
    with open(os.path.join(root, "SHA256SUMS.txt"), "w", newline="\n") as fh:
        for f in files + [{"path": name, "sha256": sha256_of(os.path.join(root, name))}]:
            fh.write("%s  %s\n" % (f["sha256"], f["path"]))
    print("wrote %s (%d files) and SHA256SUMS.txt" % (name, len(files)))


class Result:
    def __init__(self):
        self.rows = []

    def add(self, rule, level, ok, msg):
        self.rows.append((rule, level, ok, msg))

    @property
    def failed(self):
        return any(not ok and lvl == "REQUIRED" for _, lvl, ok, _ in self.rows)


def verify(root):
    R = Result()
    mpath = os.path.join(root, manifest_name(root))
    if not os.path.exists(mpath):
        R.add("X-10", "REQUIRED", False, "no manifest.json (or delivery.json in a submitted delivery) at the top of the package")
        return report(R)
    with open(mpath, encoding="utf-8") as fh:
        man = json.load(fh)
    here = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(here, "..", "schemas", "manifest.schema.json")
    try:
        import jsonschema
        with open(schema_path) as fh:
            schema = json.load(fh)
        errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(man), key=lambda e: list(e.path))
        for e in errs[:10]:
            R.add("X-10", "REQUIRED", False, "manifest: %s: %s" % ("/".join(map(str, e.path)) or "(top)", e.message[:160]))
        if not errs:
            R.add("X-10", "REQUIRED", True, "manifest matches the schema")
    except ImportError:
        R.add("X-10", "RECOMMENDED", True, "jsonschema not installed; schema check skipped")

    d = man.get("delivery", {})
    if not SEMVER.match(str(d.get("version", ""))):
        R.add("X-30", "RECOMMENDED", False, "delivery version %r is not a SemVer string" % d.get("version"))
    else:
        R.add("X-30", "RECOMMENDED", True, "delivery version %s" % d["version"])
    if not STAMP.match(str(d.get("created", ""))):
        R.add("X-30", "RECOMMENDED", False, "delivery created %r should look like 2026-10-22T10:00:00Z" % d.get("created"))

    listed = {f["path"]: f for f in man.get("files", [])}
    bad = []
    for rel, f in listed.items():
        if rel.startswith("/") or ".." in rel.split("/"):
            bad.append("unsafe path " + rel)
            continue
        full = os.path.join(root, rel)
        if not os.path.exists(full):
            bad.append("missing " + rel)
        elif os.path.getsize(full) != f["bytes"]:
            bad.append("size differs " + rel)
        elif sha256_of(full) != f["sha256"]:
            bad.append("hash differs " + rel)
    on_disk = {x["path"] for x in scan(root)}
    extra = sorted(on_disk - set(listed))
    if bad:
        R.add("X-11", "REQUIRED", False, "%d listed file(s) wrong, first: %s" % (len(bad), bad[0]))
    else:
        R.add("X-11", "REQUIRED", True, "all %d listed files exist and match their hash and size" % len(listed))
    if extra:
        R.add("X-12", "REQUIRED", False, "%d file(s) on disk are not in the manifest, first: %s" % (len(extra), extra[0]))
    else:
        R.add("X-12", "REQUIRED", True, "no unlisted files")
    sums = os.path.join(root, "SHA256SUMS.txt")
    if not os.path.exists(sums):
        R.add("X-11", "REQUIRED", False, "no SHA256SUMS.txt")
    else:
        mism = 0
        for ln in open(sums):
            if not ln.strip():
                continue
            h, _, rel = ln.rstrip("\n").partition("  ")
            if not os.path.exists(os.path.join(root, rel)) or sha256_of(os.path.join(root, rel)) != h:
                mism += 1
        R.add("X-11", "REQUIRED", mism == 0, "SHA256SUMS.txt matches the files" if not mism else "%d line(s) of SHA256SUMS.txt do not match" % mism)

    masters = [p for p, f in listed.items() if f["role"] == "master-ifc"]
    if d.get("kind") and set(d["kind"]) & {"building", "mixed"}:
        R.add("X-13", "REQUIRED", len(masters) == 1, "exactly one master IFC file" if len(masters) == 1 else "%d master IFC files; exactly one is required" % len(masters))

    cap = rpt.param("package.maxPackageMegabytes")
    total = sum(f["bytes"] for f in listed.values())
    if cap is not None:
        R.add("X-14", "REQUIRED", total <= cap * 1048576, "package is %.1f MB (profile cap %g MB)" % (total / 1048576.0, cap))
    # provenance and licence for every asset group (X-20, X-21)
    prov = {p.get("asset") for p in man.get("provenance", [])}
    groups = set()
    for rel, f in listed.items():
        if f["role"] in ("texture-map", "texture-set-description"):
            groups.add(os.path.dirname(rel))
        if f["role"] in ("item-ifc", "item-description", "item-preview"):
            groups.add(os.path.dirname(rel))
        if f["role"] in ("master-ifc", "alternate-ifc", "terrain-patch", "terrain-sidecar"):
            groups.add(rel)
    lacking = sorted(g for g in groups if g not in prov)
    need_prov = rpt.param("package.requireProvenance", True)
    need_lic = rpt.param("package.requireLicence", True)
    R.add("X-20", "REQUIRED", not (lacking and need_prov), "every texture set, item and IFC file has a provenance entry" if not lacking else
          "no provenance entry for %d asset(s), first: %s" % (len(lacking), lacking[0]))
    nolic = [p.get("asset") for p in man.get("provenance", []) if not str(p.get("licence", "")).strip() or not str(p.get("source", "")).strip()]
    R.add("X-21", "REQUIRED", not (nolic and need_lic), "every provenance entry states source and licence" if not nolic else
          "provenance entry without source or licence: %s" % nolic[0])
    lic = man.get("licence", {})
    R.add("X-21", "REQUIRED", bool(str(lic.get("statement", "")).strip()) or not need_lic, "a licence statement is present" if lic.get("statement") else "no licence statement")

    # terrain: the source version is pinned and agrees with the sidecar, the site request and the check report of the master (X-23)
    terrain_files = [p for p, f in listed.items() if f["role"] in ("terrain-patch", "terrain-sidecar", "site-request")]
    mt = man.get("terrain")
    if rpt.extension_enabled("terrain") or mt or terrain_files:
        probs = []

        def read_json(rel):
            try:
                with open(os.path.join(root, rel), encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (OSError, ValueError):
                probs.append("%s cannot be read as JSON" % rel)
                return None
            if not isinstance(doc, dict):
                probs.append("%s is not a JSON object" % rel)
                return None
            return doc
        if not isinstance(mt, dict):
            probs.append("the manifest has no terrain section")
        elif not all(isinstance(mt.get(k), dict) for k in ("patch", "sidecar", "package")):
            probs.append("terrain.patch, terrain.sidecar and terrain.package must each be an object")
        else:
            side = None
            sp = mt["sidecar"].get("path")
            pp = mt["patch"].get("path")
            if pp not in listed or listed[pp]["role"] != "terrain-patch":
                probs.append("terrain.patch.path %r is not a listed terrain patch" % pp)
            elif listed[pp]["sha256"] != mt["patch"].get("sha256"):
                probs.append("terrain.patch.sha256 differs from the listed patch file")
            if sp not in listed or listed[sp]["role"] != "terrain-sidecar":
                probs.append("terrain.sidecar.path %r is not a listed sidecar" % sp)
            else:
                side = read_json(sp)
            if side is not None:
                try:
                    import jsonschema
                    with open(os.path.join(here, "..", "schemas", "terrain-patch.schema.json"), encoding="utf-8") as fh:
                        errs = list(jsonschema.Draft7Validator(json.load(fh)).iter_errors(side))
                    if errs:
                        probs.append("the sidecar does not match its schema: %s" % errs[0].message[:120])
                except ImportError:
                    pass
                if side.get("package") != mt.get("package"):
                    probs.append("terrain.package differs from the sidecar's package (name, version, hash)")
                if side.get("patch", {}).get("sha256") != mt.get("patch", {}).get("sha256"):
                    probs.append("the sidecar's patch hash differs from terrain.patch.sha256")
            for q in (pp, sp):
                if q in listed and q not in prov:
                    probs.append("no provenance entry for %s" % q)
            rep_rel = man.get("checks", {}).get("report")
            rep_doc = read_json(rep_rel) if rep_rel in listed else None
            if rep_doc is not None:
                pins = rep_doc.get("terrain")
                if not isinstance(pins, dict):
                    probs.append("the check report of the master records no terrain source (was the terrain extension on?)")
                else:
                    for rq in (p for p, f in listed.items() if f["role"] == "site-request"):      # the request's placement is the file's
                        doc = read_json(rq)
                        if doc is None:
                            continue
                        want = {"FloorHeightAboveSeaMetres": doc.get("finishedFloorElevationMetres"), "AzimuthDegrees": doc.get("buildingAzimuthDegrees"),
                                "EastingMetres": doc.get("buildingOrigin", {}).get("x"), "NorthingMetres": doc.get("buildingOrigin", {}).get("y")}
                        for key, val in want.items():
                            if not isinstance(pins.get(key), (int, float)) or not isinstance(val, (int, float)) or abs(pins[key] - val) > 1e-6:
                                probs.append("%s places the building differently from the master file (%s: %r in the file, %r in the request)" % (
                                    rq, key, pins.get(key), val))
                                break
                    pkg, pat = mt.get("package", {}), mt.get("patch", {})
                    for key, want in (("PackageName", pkg.get("name")), ("PackageVersion", pkg.get("version")), ("PackageSha256", pkg.get("sha256")),
                                      ("PatchSha256", pat.get("sha256"))):
                        if pins.get(key) != want:
                            probs.append("the master file was built on another terrain source: %s is %r in the file and %r in the manifest" % (
                                key, pins.get(key), want))
                            break
        R.add("X-23", "REQUIRED", not probs, "terrain source pinned in the manifest and equal to the sidecar, the request and the master" if not probs else probs[0])

    # the check report belongs to the master file (X-40)
    chk = man.get("checks", {})
    rep = chk.get("report")
    if masters:
        if not rep or rep not in listed:
            R.add("X-40", "REQUIRED", False, "the manifest names no check report that is part of the package")
        else:
            with open(os.path.join(root, rep), encoding="utf-8") as fh:
                r = json.load(fh)
            same = r.get("sha256") == listed[masters[0]]["sha256"]
            R.add("X-40", "REQUIRED", same and r.get("result") == "pass",
                  "the check report is for this master file and passed" if same and r.get("result") == "pass" else
                  "the check report is for a different file or did not pass (result %s)" % r.get("result"))
    return report(R)


OPTS = {"json": False, "report": None, "root": ""}


def report(R):
    fs = []
    for rule, lvl, ok, msg in R.rows:
        lvl = rpt.level_of(rule)
        if lvl == "OFF":
            continue
        fs.append(rpt.finding(rule, "pass" if ok else ("fail" if lvl == "REQUIRED" else "warn"), msg, file=manifest_name(OPTS["root"]), level=lvl))
    rep = rpt.make_report("build_package.py", "2.3.0", {"path": os.path.basename(os.path.abspath(OPTS["root"]))}, fs)
    if OPTS["report"]:
        rpt.write(rep, OPTS["report"])
    if OPTS["json"]:
        print(json.dumps(rep, indent=1))
    else:
        for f in fs:
            print("%-4s %-5s %-11s %s" % ("ok" if f["status"] in ("pass", "info") else ("FAIL" if f["status"] == "fail" else "warn"), f["rule"], f["level"], f["message"]))
        print("package: %s" % rep["result"].upper())
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--json"]
    OPTS["json"] = "--json" in sys.argv[1:]
    if "--profile" in argv:
        i = argv.index("--profile")
        rpt.load_profile(argv[i + 1])
        del argv[i:i + 2]
    if "--report" in argv:
        i = argv.index("--report")
        OPTS["report"] = argv[i + 1]
        del argv[i:i + 2]
    mname = "manifest.json"
    if "--manifest-name" in argv:
        i = argv.index("--manifest-name")
        mname = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) >= 3 and argv[0] == "init":
        init(argv[1], argv[2], mname)
    elif len(argv) == 2 and argv[0] == "verify":
        OPTS["root"] = argv[1]
        if not os.path.isdir(argv[1]):
            rep = rpt.make_report("build_package.py", "2.3.0", {"path": argv[1]}, [], error="input not found: %s" % argv[1])
            print(json.dumps(rep, indent=1) if OPTS["json"] else "ERROR input not found: " + argv[1])
            sys.exit(rep["exitCode"])
        verify(argv[1])
    else:
        print(__doc__)
        sys.exit(2)
