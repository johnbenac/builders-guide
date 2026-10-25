#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the proofs of a delivery (rules X-79 to X-86): the GLB exports, their validation report, the renders and the manifest that ties them.

    python3 tools/check_proofs.py DELIVERY_DIR [--profile PROFILE.json] [--reproduce] [--json] [--out REPORT.json]

Without --reproduce the check reads files only (hashes, sizes, schema, coverage, metadata, a fresh validation of the GLB files) and takes
seconds. With --reproduce it also rebuilds the GLB files from the delivered IFC, items and texture sets and compares the bytes, and re-renders
every picture from the delivered GLB files and compares it with the delivered picture within `proofs.renderTolerance` (X-86); that needs
ifcopenshell, numpy, Pillow and shapely, and takes about as long as tools/build_proofs.py. When the libraries are missing the reproduction is
reported as skipped (an `info` finding) and never as passed.

X-79 manifest, listed files and nothing else in proofs/; X-81 GLB coverage, sources and a passing validation report; X-82 render coverage
(levels, room kinds, exterior, components); X-83 every render traced to a delivered GLB by hash; X-84 pixel and size limits; X-85 no personal
data or paths in images or GLB files; X-86 reproducibility. (X-80, the GLB checks, is tools/validate_glb.py, which this tool runs.)
Exit codes as in report.py: 0 no REQUIRED failure, 1 at least one, 2 wrong command line, 3 the folder could not be read.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import glbkit  # noqa: E402
import proofkit  # noqa: E402
import report as rpt  # noqa: E402

VERSION = "2.4.0"


def sha_file(path):
    return rpt.sha256_file(path)


def check(delivery, reproduce=False):
    F = []

    def add(rule, ok, msg, **kw):
        F.append(rpt.finding(rule, "pass" if ok else ("fail" if rpt.level_of(rule) == "REQUIRED" else "warn"), msg, **kw))

    def info(rule, msg, **kw):
        F.append(rpt.finding(rule, "info", msg, **kw))
    slug = os.path.basename(os.path.abspath(delivery))
    P = lambda k, d=None: rpt.param("proofs." + k, d)  # noqa: E731
    mpath = os.path.join(delivery, "proofs", "manifest.json")
    if not os.path.isfile(mpath) or os.path.islink(mpath):
        add("X-79", False, "there is no proofs/manifest.json", file="proofs/manifest.json")
        return rpt.make_report("check_proofs.py", VERSION, {"path": slug}, F)
    try:
        man = proofkit.load_json(mpath)
    except (ValueError, OSError, RecursionError):
        add("X-79", False, "proofs/manifest.json is not valid JSON", file="proofs/manifest.json")
        return rpt.make_report("check_proofs.py", VERSION, {"path": slug}, F)
    # ---- X-79 schema, listed files, nothing else
    problems = []
    try:
        import jsonschema
        sch = proofkit.load_json(os.path.join(rpt.ROOT, "schemas", "proofs.schema.json"))
        for e in sorted(jsonschema.Draft7Validator(sch).iter_errors(man), key=lambda e: list(e.path))[:5]:
            problems.append("manifest: %s: %s" % ("/".join(map(str, e.path)) or "(top)", e.message[:140]))
    except ImportError:
        info("X-79", "jsonschema is not installed; the manifest was not validated against schemas/proofs.schema.json")
    if problems:
        add("X-79", False, problems[0], file="proofs/manifest.json")
        return rpt.make_report("check_proofs.py", VERSION, {"path": slug}, F)
    listed = {}
    for g in man["glb"]:
        listed[g["path"]] = (g["sha256"], g["bytes"])
    v = man["validation"]
    listed[v["path"]] = (v["sha256"], v["bytes"])
    for r in man["renders"]:
        listed[r["path"]] = (r["sha256"], r["bytes"])
    bad = []
    for rel, (sha, nbytes) in sorted(listed.items()):
        p = os.path.join(delivery, rel)
        if ".." in rel.split("/") or not os.path.isfile(p) or os.path.islink(p):
            bad.append("%s is listed but missing" % rel)
        elif os.path.getsize(p) != nbytes:
            bad.append("%s has %d bytes, the manifest says %d" % (rel, os.path.getsize(p), nbytes))
        elif sha_file(p) != sha:
            bad.append("%s differs from the hash in the manifest" % rel)
    on_disk = []
    for base, dirs, names in os.walk(os.path.join(delivery, "proofs")):
        dirs.sort()
        for n in sorted(names):
            on_disk.append(os.path.relpath(os.path.join(base, n), delivery).replace(os.sep, "/"))
    extra = sorted(set(on_disk) - set(listed) - {"proofs/manifest.json"})
    if extra:
        bad.append("%d file(s) in proofs/ are not in the manifest, first: %s" % (len(extra), extra[0]))
    if len(listed) != len(man["glb"]) + 1 + len(man["renders"]):
        bad.append("a path is listed twice in the manifest")
    if man["delivery"]["id"] != slug:
        bad.append("the manifest is for delivery %r, not %r" % (man["delivery"]["id"], slug))
    add("X-79", not bad, "the manifest matches its schema, lists %d GLB file(s), the validation report and %d render(s), all present with their hash, and nothing else is in proofs/" %
        (len(man["glb"]), len(man["renders"])) if not bad else bad[0], file="proofs/manifest.json")
    glb_by_path = {g["path"]: g for g in man["glb"]}
    # ---- X-81 sources, coverage by GLB, validation report
    p81 = []
    src_now = {}
    for s in man["sources"]:
        fp = os.path.join(delivery, s["path"])
        src_now[s["path"]] = sha_file(fp) if os.path.isfile(fp) else None
        if src_now[s["path"]] is None:
            p81.append("source %s is not in the delivery" % s["path"])
        elif src_now[s["path"]] != s["sha256"]:
            p81.append("%s changed after the proofs were made (hash differs)" % s["path"])
    for g in man["glb"]:
        if src_now.get(g["source"]["path"]) not in (None, g["source"]["sha256"]) or g["source"]["path"] not in src_now:
            p81.append("%s was made from %s, which is not the delivered file" % (g["path"], g["source"]["path"]))
    try:
        import export_glb
        expected = export_glb.expected_keys(delivery)
    except Exception as exc:                       # no IFC library: the key check cannot be made
        expected = None
        info("X-81", "the list of expected GLB files could not be built (%s: %s)" % (type(exc).__name__, str(exc)[:80]))
    have = {k for g in man["glb"] for k in g["keys"]}
    if expected is not None:
        if not expected:
            p81.append("the delivery has nothing to export (no master IFC file, item or texture set)")
        missing = sorted(set(expected) - have)
        stale = sorted(have - set(expected))
        if missing:
            p81.append("%d component(s) have no GLB, first: %s" % (len(missing), missing[0]))
        if stale:
            p81.append("%d GLB key(s) stand for something that is not in the delivery, first: %s" % (len(stale), stale[0]))
    rep_path = os.path.join(delivery, v["path"])
    vrep = None
    if os.path.isfile(rep_path):
        try:
            vrep = proofkit.load_json(rep_path)
        except (ValueError, OSError):
            p81.append("the validation report is not valid JSON")
    if vrep is not None:
        if vrep.get("result") != "pass" or v["result"] != "pass" or vrep.get("summary", {}).get("requiredFailures"):
            p81.append("the stored validation report does not pass")
        in_rep = {f["path"]: f["sha256"] for f in vrep.get("files", [])}
        for g in man["glb"]:
            if in_rep.get(g["path"]) != g["sha256"]:
                p81.append("the validation report does not name %s with its current hash" % g["path"])
    add("X-81", not p81, "%d GLB file(s) cover every component, were made from the delivered files, and the validation report passes and names each by hash" % len(man["glb"])
        if not p81 else p81[0], file="proofs/manifest.json")
    # fresh validation of the GLB files (X-80 is validate_glb.py's rule; its findings are included as they are)
    try:
        import validate_glb
        specs = [{"path": os.path.join(delivery, g["path"]), "label": g["path"], "role": g["role"], "item": g["keys"][0].startswith("item:")}
                 for g in man["glb"] if os.path.isfile(os.path.join(delivery, g["path"]))]
        fresh = validate_glb.validate_files(specs, None, "off")
        for f in fresh["findings"]:
            if f["status"] in ("fail", "warn"):
                F.append(f)
        if fresh["result"] == "pass":
            F.append(rpt.finding("X-80", "pass", "all %d GLB file(s) pass tools/validate_glb.py now" % len(specs)))
    except ImportError as exc:
        info("X-80", "the GLB files were not validated again (%s)" % exc)
    # ---- X-82 coverage
    p82 = []
    rows = man["renders"]
    models = [g for g in man["glb"] if g["role"] == "model"]
    if models:
        levels_exp, rooms_exp = set(), []
        try:
            import export_glb
            for m in models:
                lv, rm = export_glb.expected_levels_and_rooms(os.path.join(delivery, m["source"]["path"]))
                levels_exp |= lv
                rooms_exp += rm
        except Exception as exc:
            levels_exp = {r["subject"]["id"] for r in rows if r["kind"] == "plan"}
            info("X-82", "levels and rooms were taken from the manifest because the IFC file could not be read (%s)" % type(exc).__name__)
        for lv in sorted(levels_exp):
            if not any(r["kind"] == "plan" and r["subject"]["id"] == lv for r in rows):
                p82.append("level %r has no plan" % lv)
        need = P("interiorViewsPerRoom", 4)
        for kind in sorted({k for _, k, _ in rooms_exp}):
            per_room = {}
            for r in rows:
                if r["kind"] == "interior" and r["subject"].get("roomKind") == kind:
                    per_room[r["subject"]["id"]] = per_room.get(r["subject"]["id"], 0) + 1
            if not per_room or max(per_room.values()) < need:
                p82.append("room kind %r has fewer than %d interior views of one room" % (kind, need))
        if sum(1 for r in rows if r["kind"] == "exterior") < P("exteriorViews", 4):
            p82.append("fewer than %d exterior views" % P("exteriorViews", 4))
    sheets = {}
    for r in rows:
        if r["kind"] == "sheet":
            sheets.setdefault(r["glb"], []).append(r)
    for g in man["glb"]:
        if g["role"] != "model" and not sheets.get(g["path"]):
            p82.append("%s (%s) has no contact sheet" % (g["names"][0] if g.get("names") else g["path"], g["keys"][0]))
    cov = man["coverage"]
    if len(cov["components"]) != sum(len(g["keys"]) for g in man["glb"] if g["role"] != "model"):
        p82.append("the coverage statement does not list every component key")
    add("X-82", not p82, "renders cover every level, every room kind, the outside and every component" if not p82 else p82[0], file="proofs/manifest.json")
    # ---- X-83 provenance
    p83 = []
    for r in rows:
        g = glb_by_path.get(r["glb"])
        pth = os.path.join(delivery, r["path"])
        if g is None:
            p83.append("%s was made from %s, which is not a GLB of the delivery" % (r["path"], r["glb"]))
        elif r["glbSha256"] != g["sha256"]:
            p83.append("%s names the GLB hash %s..., but the delivered %s has %s..." % (r["path"], r["glbSha256"][:12], g["path"], g["sha256"][:12]))
        if os.path.isfile(pth):
            try:
                w, h = proofkit.png_size(open(pth, "rb").read())
                if (w, h) != (r["width"], r["height"]):
                    p83.append("%s is %dx%d pixels, the manifest says %dx%d" % (r["path"], w, h, r["width"], r["height"]))
            except ValueError as exc:
                p83.append("%s is not a readable PNG (%s)" % (r["path"], exc))
        if not r.get("camera") or not r.get("light"):
            p83.append("%s has no camera or light recorded" % r["path"])
    add("X-83", not p83, "all %d render(s) name the delivered GLB they were made from, by hash, and match their recorded size" % len(rows) if not p83 else p83[0], file="proofs/manifest.json")
    # ---- X-84 limits
    p84 = []
    for r in rows:
        if r["width"] < P("minRenderWidth", 256):
            p84.append("%s is %d pixels wide (minimum %d)" % (r["path"], r["width"], P("minRenderWidth", 256)))
        if r["width"] * r["height"] > P("maxRenderPixels", 2097152):
            p84.append("%s has %d pixels (limit %d)" % (r["path"], r["width"] * r["height"], P("maxRenderPixels", 2097152)))
        if r["bytes"] > P("maxRenderBytes", 3145728):
            p84.append("%s is %d bytes (limit %d)" % (r["path"], r["bytes"], P("maxRenderBytes", 3145728)))
    total = sum(os.path.getsize(os.path.join(delivery, x)) for x in on_disk if os.path.isfile(os.path.join(delivery, x)))
    if total > P("maxProofBytes", 67108864):
        p84.append("proofs/ holds %d bytes (limit %d)" % (total, P("maxProofBytes", 67108864)))
    add("X-84", not p84, "renders are within the pixel and size limits; proofs/ is %d bytes" % total if not p84 else p84[0], file="proofs/manifest.json")
    # ---- X-85 metadata, in every image and GLB of the delivery
    p85 = []
    render_paths = {r["path"] for r in rows}
    for base, dirs, names in os.walk(delivery):
        dirs.sort()
        for n in sorted(names):
            full = os.path.join(base, n)
            rel = os.path.relpath(full, delivery).replace(os.sep, "/")
            ext = n.rsplit(".", 1)[-1].lower()
            if os.path.islink(full) or ext not in ("png", "jpg", "glb"):
                continue
            with open(full, "rb") as fh:
                data = fh.read()
            if ext in ("png", "jpg"):
                for m in proofkit.image_metadata_problems(data, strict=rel in render_paths)[:2]:
                    p85.append("%s: %s" % (rel, m))
            else:
                try:
                    doc, bn = glbkit.split_glb(data)
                except glbkit.Failed:
                    continue
                for ptr, text in proofkit.walk_strings(doc):
                    for kind, ex in proofkit.find_leaks(text):
                        p85.append("%s: %s holds a %s (%r)" % (rel, ptr, kind, ex))
                for i, im in enumerate(doc.get("images", []) or []):
                    if isinstance(im.get("bufferView"), int) and im["bufferView"] < len(doc.get("bufferViews", [])):
                        vw = doc["bufferViews"][im["bufferView"]]
                        raw = bn[vw.get("byteOffset", 0):vw.get("byteOffset", 0) + vw["byteLength"]]
                        for m in proofkit.image_metadata_problems(raw, strict=False)[:2]:
                            p85.append("%s: embedded image %d: %s" % (rel, i, m))
    add("X-85", not p85, "no image or GLB file holds metadata that can carry personal data or a path" if not p85 else p85[0], file="proofs/manifest.json")
    # ---- X-86 reproducibility
    if not reproduce:
        info("X-86", "reproduction was not run; use --reproduce (continuous integration does)", file="proofs/manifest.json")
    else:
        reproduce_checks(delivery, man, F, add, info)
    return rpt.make_report("check_proofs.py", VERSION, {"path": slug}, F, counts={"glb": len(man["glb"]), "renders": len(rows), "proofBytes": total})


def glb_close(a, b, tol=1e-4):
    """(True, "") when two GLB files hold the same nodes with the same triangles to within `tol` metres; otherwise (False, why)."""
    import numpy as np
    try:
        da, ba = glbkit.split_glb(a)
        db, bb = glbkit.split_glb(b)
        ta, tb = glbkit.triangles_of(da, ba), glbkit.triangles_of(db, bb)
    except (glbkit.Failed, KeyError, ValueError) as exc:
        return False, "unreadable (%s)" % exc
    if [t["node"] for t in ta] != [t["node"] for t in tb]:
        return False, "the nodes differ"
    for x, y in zip(ta, tb):
        if x["tri"].shape != y["tri"].shape:
            return False, "node %s has a different number of triangles" % x["node"]
        if x["tri"].size and np.abs(x["tri"] - y["tri"]).max() > tol:
            return False, "node %s differs by more than %g m" % (x["node"], tol)
    return True, ""


def reproduce_checks(delivery, man, F, add, info):
    try:
        import importlib
        for mod in ("numpy", "PIL", "ifcopenshell", "shapely"):
            importlib.import_module(mod)
        import export_glb
        import render
    except ImportError as exc:
        info("X-86", "reproduction skipped: the toolchain is not available (%s)" % exc, file="proofs/manifest.json")
        return
    import build_proofs
    libs = build_proofs.library_versions()
    # Bytes must be equal when the library version and the processor architecture are the ones the proofs were made with; otherwise the
    # floating-point results of the geometry kernel may differ in the last bits, and the files are compared by their triangles instead.
    same_ifc = (man["tools"]["libraries"].get("ifcopenshell") == libs.get("ifcopenshell")
                and man["tools"]["libraries"].get("architecture") == libs.get("architecture"))
    problems, notes = [], []
    # 1 the GLB files again from the delivered source
    try:
        res = export_glb.export_delivery(os.path.abspath(delivery))
    except Exception as exc:
        add("X-86", False, "the GLB files could not be rebuilt from the delivered files: %s" % str(exc)[:160], file="proofs/manifest.json")
        return
    now = {"proofs/glb/" + e["rel"]: e for e in res["models"] + res["components"] + res["materials"]}
    if set(now) != {g["path"] for g in man["glb"]}:
        problems.append("a rebuild gives a different set of GLB files (%d, the manifest lists %d)" % (len(now), len(man["glb"])))
    for g in man["glb"]:
        e = now.get(g["path"])
        if e is None:
            continue
        if e["sha256"] == g["sha256"]:
            continue
        if same_ifc:
            problems.append("%s: a rebuild gives different bytes on the same toolchain (%s... against %s...)" % (g["path"], e["sha256"][:12], g["sha256"][:12]))
        else:
            with open(os.path.join(delivery, g["path"]), "rb") as fh:
                ok, why = glb_close(fh.read(), e["glb"])
            (notes if ok else problems).append("%s: bytes differ (ifcopenshell %s on %s was used for the delivery, %s on %s now); %s" % (
                g["path"], man["tools"]["libraries"].get("ifcopenshell", "?"), man["tools"]["libraries"].get("architecture", "?"),
                libs.get("ifcopenshell", "?"), libs.get("architecture", "?"), "the triangles agree within 0.1 mm" if ok else why))
    # 2 the pictures again from the delivered GLB files
    tol = dict(rpt.param("proofs.renderTolerance", {"meanAbsLevels": 0.5, "differingFraction": 0.001, "differenceLevels": 8}))
    files = []
    for g in man["glb"]:
        sub = None
        if g["role"] != "model":
            sub = next((r["subject"] for r in man["renders"] if r["kind"] == "sheet" and r["glb"] == g["path"]), None)
        files.append({"path": os.path.join(delivery, g["path"]), "rel": g["path"], "role": g["role"], "subject": sub})
    scale = 1.0
    first = next((r for r in man["renders"] if r["kind"] == "plan"), None) or next(iter(man["renders"]))
    if first["kind"] == "plan":
        scale = first["width"] / float(render.PLAN_SIZE[0])
    try:
        recs = render.render_set(files, scale)
    except Exception as exc:
        add("X-86", False, "the renders could not be rebuilt from the delivered GLB files: %s" % str(exc)[:160], file="proofs/manifest.json")
        return
    by_name = {"proofs/renders/" + r["name"]: r for r in recs}
    stored = {r["path"]: r for r in man["renders"]}
    if set(by_name) != set(stored):
        problems.append("a re-render gives a different set of pictures (%d, the manifest lists %d)" % (len(by_name), len(stored)))
    worst = None
    for path, r in sorted(by_name.items()):
        if path not in stored:
            continue
        with open(os.path.join(delivery, path), "rb") as fh:
            a = proofkit.decode_png(fh.read())
        b = proofkit.decode_png(r["png"])
        ok, st = proofkit.compare_pictures(a, b, tol)
        if not ok:
            problems.append("%s: the re-render differs from the delivered picture (%s)" % (path, ", ".join("%s %s" % kv for kv in sorted(st.items()))))
        elif worst is None or st["meanAbsLevels"] > worst[1]:
            worst = (path, st["meanAbsLevels"])
    detail = "%d GLB file(s) rebuilt%s and %d picture(s) re-rendered within tolerance (mean difference at most %s of 255 levels)" % (
        len(now), " byte for byte" if same_ifc else " (to within 0.1 mm: another IFC library version or processor architecture)", len(by_name), worst[1] if worst else 0)
    add("X-86", not problems, detail if not problems else problems[0], file="proofs/manifest.json")
    for n in notes[:3]:
        info("X-86", n, file="proofs/manifest.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("delivery")
    ap.add_argument("--profile")
    ap.add_argument("--reproduce", action="store_true", help="rebuild the GLB files and re-render the pictures, and compare (X-86)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    rpt.load_profile(a.profile)
    if not os.path.isdir(a.delivery) or os.path.islink(a.delivery):
        rep = rpt.make_report("check_proofs.py", VERSION, {"path": a.delivery}, [], error="not a folder: %s" % a.delivery)
    else:
        rep = check(a.delivery, a.reproduce)
    if a.out:
        rpt.write(rep, a.out)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for line in rpt.text_lines(rep):
            print(line)
        s = rep["summary"]
        print("proofs: %s (%d REQUIRED failure(s), %d RECOMMENDED warning(s))" % (rep["result"].upper(), s["requiredFailures"], s["recommendedWarnings"]))
        for f in rep["findings"]:
            if f["status"] == "info":
                print("info  %s %s" % (f["rule"], f["message"]))
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    main()
