#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One entry point: run every check that applies to a deliverable and print one report.

    python3 tools/check_all.py PATH [--type auto|building|material|furniture|package]
                               [--profile PROFILE.json] [--finish-schedule FILE]
                               [--json] [--out REPORT.json]

PATH is one of
    building    a master .ifc file
    material    a folder with finishes/ (texture sets, finish-schedule.json, library.json) or a finishes folder itself
    furniture   a folder with items/<itemId>/ or an items folder itself
    package     a delivery package folder (has manifest.json); everything inside it is checked too
--type auto (the default) picks from PATH. The report has schema check-report/1 (schemas/check-report.schema.json): the
findings of every check, each with its rule id, level, location, message and fix_hint, plus the full sub-reports under
`reports`. The report names the profile it was checked against (profiles/default.json unless --profile is given). Exit codes: 0 no REQUIRED rule failed, 1 at least one did, 2 wrong command line, 3 an input could not be read.
"""
import argparse
import copy
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report as rpt  # noqa: E402

VERSION = "2.1.0"
ROOT = rpt.ROOT


PROFILE = [None]


def run(script, *args):
    extra = ["--profile", PROFILE[0]] if PROFILE[0] else []
    p = subprocess.run([sys.executable, os.path.join(HERE, script), *args, *extra, "--json"], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except ValueError:
        return rpt.make_report(script, "?", {"path": " ".join(args)}, [], error="%s printed no JSON (exit %d): %s" % (script, p.returncode, (p.stderr or p.stdout)[-300:]))


def validate(schema_rel, doc_path, rule, level, name):
    """Schema check of one JSON file; returns a report."""
    findings, error = [], None
    try:
        import jsonschema
    except ImportError:
        return rpt.make_report("check_all.py", VERSION, {"path": doc_path}, [rpt.finding(rule, "info", "jsonschema is not installed; %s was not validated" % name)])
    try:
        with open(doc_path, encoding="utf-8") as fh:
            doc = json.load(fh)
        with open(os.path.join(ROOT, schema_rel), encoding="utf-8") as fh:
            schema = json.load(fh)
    except (OSError, ValueError) as exc:
        findings.append(rpt.finding(rule, "fail" if level == "REQUIRED" else "warn", "%s cannot be read as JSON: %s" % (name, exc), file=os.path.basename(doc_path), level=level))
        return rpt.make_report("check_all.py", VERSION, {"path": doc_path}, findings)
    errs = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    for e in errs[:15]:
        findings.append(rpt.finding(rule, "fail" if level == "REQUIRED" else "warn",
                                    "%s: %s: %s" % (name, "/".join(map(str, e.path)) or "(top)", e.message[:200]),
                                    file=os.path.basename(doc_path), level=level))
    if not errs:
        findings.append(rpt.finding(rule, "pass", "%s matches %s" % (name, schema_rel), file=os.path.basename(doc_path), level=level))
    return rpt.make_report("check_all.py", VERSION, {"path": doc_path}, findings)


def find_master(pkg):
    m = [p for p in glob.glob(os.path.join(pkg, "ifc", "*.ifc"))]
    return m[0] if len(m) == 1 else None


def building(path, a):
    reps = []
    args = [path]
    if a.finish_schedule:
        args += ["--finish-schedule", a.finish_schedule]
    reps.append(run("check_ifc.py", *args))
    return reps


def material(folder, a):
    reps = []
    fin = folder if os.path.isdir(os.path.join(folder, "textures")) else os.path.join(folder, "finishes")
    for s in sorted(glob.glob(os.path.join(fin, "textures", "*", ""))):
        reps.append(run("check_texture_set.py", s.rstrip(os.sep)))
    sched = os.path.join(fin, "finish-schedule.json")
    if os.path.exists(sched):
        reps.append(validate("schemas/finish-schedule.schema.json", sched, "D-60", "REQUIRED", "finish-schedule.json"))
    lib = os.path.join(fin, "library.json")
    if os.path.exists(lib):
        reps.append(validate("schemas/material-library.schema.json", lib, "X-41", "RECOMMENDED", "library.json"))
    if not reps:
        reps.append(rpt.make_report("check_all.py", VERSION, {"path": folder}, [], error="no texture sets or finish schedule found under %s" % folder))
    return reps


def furniture(folder, a):
    items = folder if os.path.basename(os.path.abspath(folder)) == "items" else os.path.join(folder, "items")
    reps = [run("check_item.py", d.rstrip(os.sep)) for d in sorted(glob.glob(os.path.join(items, "*", "")))]
    if not reps:
        reps.append(rpt.make_report("check_all.py", VERSION, {"path": folder}, [], error="no items found under %s" % items))
    return reps


def package(pkg, a):
    reps = [run("build_package.py", "verify", pkg)]
    m = find_master(pkg)
    if m:
        sched = os.path.join(pkg, "finishes", "finish-schedule.json")
        b = copy.copy(a)
        b.finish_schedule = b.finish_schedule or (sched if os.path.exists(sched) else None)
        reps += building(m, b)
        for sch, rel in (("schemas/terrain-patch.schema.json", "terrain/patch.json"), ("schemas/site-request.schema.json", "terrain/site-request.json")):
            if os.path.exists(os.path.join(pkg, rel)):
                reps.append(validate(sch, os.path.join(pkg, rel), "B-137", "REQUIRED", rel))
        meta = os.path.join(pkg, "tables", "building.json")
        if os.path.exists(meta):
            reps.append(validate("schemas/building-metadata.schema.json", meta, "X-41", "RECOMMENDED", "building.json"))
    if os.path.isdir(os.path.join(pkg, "finishes")):
        reps += material(pkg, a)
    if os.path.isdir(os.path.join(pkg, "items")):
        reps += furniture(pkg, a)
    return reps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--type", default="auto", choices=["auto", "building", "material", "furniture", "package"])
    ap.add_argument("--profile", help="consumer profile (profiles/profile.schema.json); default profiles/default.json")
    ap.add_argument("--finish-schedule")
    ap.add_argument("--json", action="store_true", help="print the JSON report")
    ap.add_argument("--out", help="also write the JSON report to this file")
    a = ap.parse_args()
    PROFILE[0] = a.profile
    rpt.load_profile(a.profile)
    p = a.path
    if not os.path.exists(p):
        rep = rpt.make_report("check_all.py", VERSION, {"path": p}, [], error="input not found: %s" % p)
        print(json.dumps(rep, indent=1) if a.json else "ERROR input not found: %s" % p)
        sys.exit(rep["exitCode"])
    t = a.type
    if t == "auto":
        if os.path.isfile(p) and p.endswith(".ifc"):
            t = "building"
        elif os.path.isdir(p) and os.path.exists(os.path.join(p, "manifest.json")):
            t = "package"
        elif os.path.isdir(p) and (os.path.isdir(os.path.join(p, "textures")) or os.path.isdir(os.path.join(p, "finishes"))):
            t = "material"
        elif os.path.isdir(p) and (os.path.isdir(os.path.join(p, "items")) or os.path.basename(os.path.abspath(p)) == "items"):
            t = "furniture"
        else:
            rep = rpt.make_report("check_all.py", VERSION, {"path": p}, [], error="cannot tell what %s is; give --type" % p)
            print(json.dumps(rep, indent=1) if a.json else "ERROR " + rep["error"])
            sys.exit(rep["exitCode"])
    reps = {"building": building, "material": material, "furniture": furniture, "package": package}[t](p, a)
    findings, errors = [], []
    for r in reps:
        for f in r["findings"]:
            g = dict(f)
            g["source"] = r["tool"]
            findings.append(g)
        if r["result"] == "error":
            errors.append("%s: %s" % (r["tool"], r.get("error", "error")))
    rep = rpt.make_report("check_all.py", VERSION, {"path": os.path.basename(os.path.abspath(p)), "type": t}, findings,
                          counts={"checks": len(reps)}, extra={"reports": reps}, error="; ".join(errors) if errors else None)
    if errors and rep["summary"]["requiredFailures"]:
        rep["exitCode"] = 1
        rep["result"] = "fail"
    if a.out:
        rpt.write(rep, a.out)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for line in rpt.text_lines(rep):
            print(line)
        s = rep["summary"]
        print("%s: %s (%d REQUIRED failure(s), %d RECOMMENDED warning(s), %d check(s))" % (t, rep["result"].upper(), s["requiredFailures"],
              s["recommendedWarnings"], len(reps)))
        for e in errors:
            print("ERROR " + e)
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    main()
