#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the sample submitted delivery `deliveries/example-room/` (guide 4, section 8) from the worked example of guide 5.

    python3 tools/make_sample_delivery.py [DELIVERIES_DIR]        default: deliveries/ in this repository

Runs tools/run_example.py in a temporary folder, then turns its package into a submission: the manifest becomes `delivery.json`
with a `submission` block, licences become CC BY 4.0, a preview picture is drawn with tools/preview.py (needs
tools/requirements-preview.txt), `notes/open-points.md` is added, and the proofs (GLB files, validation report, renders and manifest) are
built with tools/build_proofs.py. The output is deterministic. Refuses to overwrite an existing
delivery folder.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_all  # noqa: E402  (the one place the version of the set is written)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SLUG = "example-room"


def py(script, *args):
    p = subprocess.run([sys.executable, os.path.join(HERE, script), *args], capture_output=True, text=True)
    if p.returncode:
        sys.exit("FAILED %s %s\n%s%s" % (script, " ".join(args), p.stdout[-800:], p.stderr[-800:]))


def main():
    dest_root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "deliveries")
    dest = os.path.join(dest_root, SLUG)
    if os.path.exists(dest):
        sys.exit("%s exists; remove it first" % dest)
    with tempfile.TemporaryDirectory(prefix="sample-delivery-") as tmp:
        py("run_example.py", tmp)
        pkg = os.path.join(tmp, "example-room-1.0.0")
        with open(os.path.join(tmp, "package-meta.json"), encoding="utf-8") as fh:
            meta = json.load(fh)
        os.makedirs(os.path.join(pkg, "previews"))
        pv = os.path.join(tmp, "pv")
        py("preview.py", os.path.join(pkg, "ifc", "example-room-master.ifc"), pv)
        shutil.copyfile(os.path.join(pv, "iso.png"), os.path.join(pkg, "previews", "iso.png"))
        with open(os.path.join(pkg, "notes", "open-points.md"), "w", newline="\n") as fh:
            fh.write("# Open points\n\nNone. The geometry is deliberately small: it exists to show the layout of a submitted delivery.\n")
        with open(os.path.join(pkg, "finishes", "SOURCES.csv"), "w", newline="\n") as fh:
            fh.write("asset,type,source,licence,notes\nfinishes/textures/plaster_example,texture set,"
                     "\"procedural: tools/make_sample_texture_set.py, seed 7\",CC-BY-4.0,no input images\n")
        meta["delivery"].update({"id": SLUG, "title": "Example room (sample submission)", "version": "1.0.0"})
        meta["profile"] = {"name": "default", "version": json.load(open(os.path.join(ROOT, "profiles", "default.json")))["version"]}
        for p in meta["provenance"]:
            p["licence"] = "CC-BY-4.0"
            p["author"] = "Example contributors"
        meta["provenance"].append({"asset": "previews/iso.png", "type": "other", "source": "original: tools/preview.py", "author": "Example contributors", "licence": "CC-BY-4.0"})
        meta["author"] = {"organisation": "Example contributors", "role": "sample author", "contact": "example-contributor"}
        meta["licence"] = {"statement": "Everything in this delivery is offered under CC BY 4.0."}
        meta["submission"] = {
            "title": "Example room (sample submission)",
            "summary": "One room with a door, a window, a work table, a wall covering and a ceiling luminaire, built from the worked example.",
            "submitter": {"handle": "example-contributor"},
            "licence": "CC-BY-4.0",
            "profile": meta["profile"],
            "toolVersions": {"authoring-guide-set": gen_all.VERSION, "ifcopenshell": __import__("ifcopenshell").version},
            "attestation": {"ownWork": True, "mayLicense": True, "noRestrictedContent": True}}
        mp = os.path.join(tmp, "meta.json")
        with open(mp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(meta, fh, indent=2)
            fh.write("\n")
        os.remove(os.path.join(pkg, "manifest.json"))
        os.remove(os.path.join(pkg, "SHA256SUMS.txt"))
        py("build_package.py", "init", pkg, mp, "--manifest-name", "delivery.json")
        os.makedirs(dest_root, exist_ok=True)
        shutil.copytree(pkg, dest)
        # the proofs are made in the final folder (their manifest names the delivery by its folder), then the package manifest is written again
        r = subprocess.run([sys.executable, os.path.join(HERE, "build_proofs.py"), dest], capture_output=True, text=True)
        if r.returncode:
            sys.exit("FAILED build_proofs.py\n%s%s" % (r.stdout[-800:], r.stderr[-800:]))
        py("build_package.py", "init", dest, mp, "--manifest-name", "delivery.json")
    print("wrote", dest)


if __name__ == "__main__":
    main()
