#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the proofs of a delivery: export -> validate -> render, written under deliveries/<slug>/proofs/ (guide 4, section 8.1).

    python3 tools/build_proofs.py DELIVERY_DIR [--profile PROFILE.json] [--scale 1.0] [--keep-going] [--json]

1. tools/export_glb.py: proofs/glb/model.glb, proofs/glb/components/*.glb, proofs/glb/materials/*.glb
2. tools/validate_glb.py (with the Khronos validator when it is installed): proofs/reports/glb-validation.json
3. tools/render.py, from the GLB files only: proofs/renders/*.png
4. proofs/manifest.json (schemas/proofs.schema.json): every file with its SHA-256 and size, the source IFC hashes, the camera and light of every
   picture, the GLB hash each picture was made from, the tools and library versions, and a coverage statement.
An existing proofs/ folder is replaced as a whole. Nothing outside proofs/ is touched: afterwards refresh the package manifest and
SHA256SUMS.txt (`python3 tools/build_package.py init DIR META.json --manifest-name delivery.json`). The output depends only on the delivered files
and the library versions; no times, no paths, no host names. Exit codes: 0 written and the validation passed, 1 written but the validation
failed (the report says what), 2 wrong command line, 3 an input could not be read or built.
"""
import argparse
import json
import os
import platform
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import export_glb  # noqa: E402
import glbkit  # noqa: E402
import render  # noqa: E402
import report as rpt  # noqa: E402
import validate_glb  # noqa: E402
from glbkit import Failed, sha256_bytes  # noqa: E402

VERSION = "2.5.0"
MAX_ROOM_NOTE = 12


def library_versions():
    out = {"architecture": platform.machine() or "unknown"}
    for mod in ("ifcopenshell", "numpy", "PIL", "shapely"):
        try:
            m = __import__(mod)
            out["pillow" if mod == "PIL" else mod] = str(getattr(m, "__version__", None) or getattr(m, "version", "?"))
        except ImportError:
            pass
    return out


def tolerance():
    return dict(rpt.param("proofs.renderTolerance", {"meanAbsLevels": 0.5, "differingFraction": 0.001, "differenceLevels": 8}))


def sheet_subject(c):
    kind = "material" if c["kind"] == "material-set" else "component"
    return {"type": kind, "id": c["keys"][0], "name": c["names"][0], "keys": c["keys"]}


def build(delivery, scale=1.0, keep_going=False):
    """Returns (manifest dict, report dict, files {relative path: bytes}). Nothing is written."""
    man_path = os.path.join(delivery, "delivery.json")
    if not os.path.exists(man_path):
        man_path = os.path.join(delivery, "manifest.json")
    dman = {}
    if os.path.exists(man_path):
        with open(man_path, encoding="utf-8") as fh:
            dman = json.load(fh)
    slug = os.path.basename(os.path.abspath(delivery))
    res = export_glb.export_delivery(os.path.abspath(delivery))
    entries = res["models"] + res["components"] + res["materials"]
    if not res["models"] and not res["components"] and not res["materials"]:
        raise Failed("the delivery holds nothing to export (no master IFC file, item or texture set)")
    files = {}
    glb_rows = []
    for role, group in (("model", res["models"]), ("component", res["components"]), ("material", res["materials"])):
        for e in group:
            rel = "proofs/glb/" + e["rel"]
            files[rel] = e["glb"]
            row = {"path": rel, "role": role, "sha256": e["sha256"], "bytes": len(e["glb"]), "triangles": e["triangles"], "kind": e["kind"], "category": e["category"],
                   "names": e["names"], "keys": e["keys"], "source": e["source"], "bounds": e.get("bounds")}
            if role == "model":
                row["nodes"] = e["nodes"]
            glb_rows.append(row)
    # validate
    import tempfile
    with tempfile.TemporaryDirectory(prefix="proofs-") as tmp:
        specs = []
        for e, row in zip(entries, glb_rows):
            p = os.path.join(tmp, row["path"])
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as fh:
                fh.write(e["glb"])
            ifc = os.path.join(delivery, e["source"]["path"]) if row["role"] == "model" else None
            specs.append({"path": p, "label": row["path"], "role": row["role"], "item": row["keys"][0].startswith("item:"), "ifc": ifc})
        vrep = validate_glb.validate_files(specs)
        vrep["target"] = {"path": slug}
        if vrep["result"] == "fail" and not keep_going:
            pass                                                       # the report is still written; the exit code says it failed
        rpt_path = "proofs/reports/glb-validation.json"
        vbytes = (json.dumps(vrep, indent=1) + "\n").encode("utf-8")
        files[rpt_path] = vbytes
        # render from the GLB files on disk (exactly what is delivered)
        rfiles = []
        for e, row in zip(entries, glb_rows):
            rfiles.append({"path": os.path.join(tmp, row["path"]), "rel": row["path"], "role": row["role"], "subject": sheet_subject(e) if row["role"] != "model" else None})
        recs = render.render_set(rfiles, scale)
    render_rows, names = [], set()
    for r in recs:
        if r["name"] in names:
            raise Failed("two renders would have the same name: %s" % r["name"])
        names.add(r["name"])
        rel = "proofs/renders/" + r["name"]
        files[rel] = r["png"]
        w, h = r["size"]
        row = {"id": r["name"][:-4], "path": rel, "sha256": sha256_bytes(r["png"]), "bytes": len(r["png"]), "width": w, "height": h, "kind": r["kind"],
               "subject": r["subject"], "glb": r["glb"], "glbSha256": r["glbSha256"], "camera": r["camera"], "light": render.LIGHT, "background": r["background"],
               "tool": {"name": "render.py", "version": render.VERSION}}
        for k in ("frames", "cellPixels", "columns", "cutHeightMetres", "azimuthDegrees", "elevationDegrees"):
            if k in r:
                row[k] = r[k]
        render_rows.append(row)
    sources = {}
    for row in glb_rows:
        sources[row["source"]["path"]] = row["source"]["sha256"]
    prof = rpt.profile_info()
    manifest = {
        "format": "proofs/1",
        "delivery": {"id": slug, "version": (dman.get("delivery") or {}).get("version", "0.0.0")},
        "tools": {"guideSet": VERSION, "exportGlb": export_glb.VERSION, "validateGlb": validate_glb.VERSION,
                  "render": {"version": render.VERSION, "backend": render.BACKEND}, "libraries": library_versions()},
        "profile": {"name": prof["name"], "version": prof["version"]},
        "conventions": {"units": "metres", "glbAxes": "y-up", "ifcAxes": "z-up", "axisConversion": glbkit.AXIS_NOTE},
        "sources": [{"path": p, "sha256": h} for p, h in sorted(sources.items())],
        "glb": glb_rows,
        "validation": {"path": rpt_path, "sha256": sha256_bytes(vbytes), "bytes": len(vbytes), "result": vrep["result"], "tool": "validate_glb.py",
                       "toolVersion": validate_glb.VERSION, "khronos": vrep.get("khronos", {"used": False}),
                       "glb": [{"path": f["path"], "sha256": f["sha256"]} for f in vrep["files"]]},
        "renderSettings": {"backend": render.BACKEND, "supersampling": render.SS, "light": render.LIGHT, "toleranceUsedByChecks": tolerance()},
        "renders": render_rows,
    }
    manifest["coverage"] = coverage(manifest, res)
    return manifest, vrep, files


def coverage(manifest, res):
    """What the renders cover, as data and as a sentence."""
    rows = manifest["renders"]
    levels = []
    for model in res["models"]:
        for lv in model["levels"]:
            levels.append({"name": lv["name"], "elevationMetres": lv["elevation"],
                           "renders": [r["path"] for r in rows if r["kind"] == "plan" and r["subject"]["id"] == lv["name"]]})
    kinds = {}
    for model in res["models"]:
        for room in model["rooms"]:
            kinds.setdefault(room["function"], []).append(room["id"])
    room_kinds = []
    for kind, ids in sorted(kinds.items()):
        shown = sorted({r["subject"]["id"] for r in rows if r["kind"] == "interior" and r["subject"].get("roomKind") == kind})
        room_kinds.append({"kind": kind, "rooms": sorted(ids), "roomsNotRendered": sorted(set(ids) - set(shown))[:MAX_ROOM_NOTE],
                           "renders": [r["path"] for r in rows if r["kind"] == "interior" and r["subject"].get("roomKind") == kind]})
    comps = []
    for e in res["components"] + res["materials"]:
        sheet = next(r["path"] for r in rows if r["kind"] == "sheet" and r["glb"] == "proofs/glb/" + e["rel"])
        for k in e["keys"]:
            comps.append({"key": k, "glb": "proofs/glb/" + e["rel"], "sheet": sheet})
    exterior = [r["path"] for r in rows if r["kind"] == "exterior"]
    n_rooms = sum(len(k["rooms"]) for k in room_kinds)
    st = ("%d level(s) each with a plan; %d room kind(s) (%s) each with interior views of the first room(s) by identifier, %d of %d room(s) in all; "
          "%d exterior view(s); %d component key(s) in %d GLB file(s), each with a contact sheet. Rooms of a kind beyond the profile's limit "
          "are not rendered; identical geometry shares one GLB and one sheet." % (
              len(levels), len(room_kinds), ", ".join(k["kind"] for k in room_kinds) or "none", sum(len(k["rooms"]) - len(k["roomsNotRendered"]) for k in room_kinds),
              n_rooms, len(exterior), len(comps), len(res["components"]) + len(res["materials"])))
    return {"statement": st, "levels": levels, "roomKinds": room_kinds, "exterior": exterior, "components": comps}


def write(delivery, manifest, files):
    base = os.path.join(delivery, "proofs")
    if os.path.lexists(base):
        shutil.rmtree(base)
    for rel, data in sorted(files.items()):
        p = os.path.join(delivery, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)
        os.chmod(p, 0o644)
    mp = os.path.join(base, "manifest.json")
    with open(mp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=True)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("delivery")
    ap.add_argument("--profile")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--keep-going", action="store_true", help="accepted for symmetry with other tools; the report is always written")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rpt.load_profile(a.profile)
    if not os.path.isdir(a.delivery) or os.path.islink(a.delivery):
        print("ERROR not a folder: %s" % a.delivery, file=sys.stderr)
        sys.exit(3)
    d = os.path.abspath(a.delivery)
    try:
        manifest, vrep, files = build(d, a.scale, a.keep_going)
    except Failed as exc:
        print("FAILED: %s" % exc, file=sys.stderr)
        sys.exit(3)
    except Exception as exc:                                   # an unreadable IFC or texture file
        print("FAILED: %s: %s" % (type(exc).__name__, str(exc)[:200]), file=sys.stderr)
        sys.exit(3)
    write(d, manifest, files)
    n_glb, n_ren = len(manifest["glb"]), len(manifest["renders"])
    total = sum(len(v) for v in files.values())
    if a.json:
        print(json.dumps({"glb": n_glb, "renders": n_ren, "bytes": total, "validation": vrep["result"], "coverage": manifest["coverage"]["statement"]}, indent=1))
    else:
        print("wrote proofs/: %d GLB file(s), %d render(s), %d bytes; GLB validation %s" % (n_glb, n_ren, total, vrep["result"].upper()))
        print(manifest["coverage"]["statement"])
        for line in rpt.text_lines(vrep):
            print(line)
        print("next: refresh the package manifest and SHA256SUMS.txt (tools/build_package.py init ... --manifest-name delivery.json)")
    sys.exit(0 if vrep["result"] == "pass" else 1)


if __name__ == "__main__":
    main()
