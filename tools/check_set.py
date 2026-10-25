#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check a copy of the guide set that someone has staged somewhere (a packet, a vendored folder, a mirror): is it the version it claims, is it whole, and
does it hold the tools the people who use it were promised?

    python3 tools/check_set.py [SET_DIR] [--expect X.Y.Z] [--require PATH ...] [--json]

SET_DIR is the top folder of the copy (default: the folder this script is in). Checks:
  * version: the newest heading of CHANGELOG.md, `version` of rules.json and MANIFEST.json, and the `VERSION` of every tool agree, and with `--expect`
    equal the stated version (a hand-over note that says "the guide is 2.3.0" and a folder that holds 2.1.0 is the typical fault);
  * integrity: every file in MANIFEST.sha256 exists and has the listed hash (a missing tool, a hand-edited tool, a half-copied folder);
  * `--require PATH` (repeatable, a path below SET_DIR such as tools/export_glb.py): the file exists. For a set that carries its own tools folder
    nothing else needs to be named: a copy that passes the integrity check holds every tool the manifest lists.
Folders such as __pycache__, work/ and dist/ and files that are not in the manifest are ignored (they are reported as `extra` with --json).

Exit codes: 0 the copy is what it says and is whole, 1 at least one check failed, 2 wrong command line, 3 SET_DIR is not a guide set.
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "2.3.0"
SKIP_DIRS = {"__pycache__", "dist", "work", "node_modules", ".git"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def versions(root):
    """{where: version string or None} for every place a version is stated."""
    out = {}
    try:
        m = re.search(r"^## (\d+\.\d+\.\d+)\b", read_text(os.path.join(root, "CHANGELOG.md")), re.M)
        out["CHANGELOG.md"] = m.group(1) if m else None
    except OSError:
        out["CHANGELOG.md"] = None
    for name in ("rules.json", "MANIFEST.json"):
        try:
            out[name] = str(json.loads(read_text(os.path.join(root, name))).get("version"))
        except (OSError, ValueError):
            out[name] = None
    tdir = os.path.join(root, "tools")
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if fn.endswith(".py"):
                m = re.search(r'^VERSION = "(\d+\.\d+\.\d+)"', read_text(os.path.join(tdir, fn)), re.M)
                if m:
                    out["tools/" + fn] = m.group(1)
    return out


def listed(root):
    """{path: sha256} of MANIFEST.sha256, or None when it is missing."""
    try:
        text = read_text(os.path.join(root, "MANIFEST.sha256"))
    except OSError:
        return None
    out = {}
    for line in text.splitlines():
        m = re.match(r"^([0-9a-f]{64})  (.+)$", line)
        if m:
            out[m.group(2)] = m.group(1)
    return out


def check(root, expect=None, require=()):
    """(problems, details): problems is a list of strings; details has the versions, counts and extra files."""
    problems = []
    vs = versions(root)
    found = {v for v in vs.values() if v}
    if None in vs.values():
        problems.append("version: not readable in %s" % ", ".join(k for k, v in vs.items() if v is None))
    if len(found) > 1:
        top = vs.get("CHANGELOG.md")
        problems.append("version: the files disagree; CHANGELOG.md says %s but %s" % (top, ", ".join("%s says %s" % (k, v) for k, v in sorted(vs.items()) if v and v != top)[:300]))
    if expect and found != {expect}:
        problems.append("version: expected %s, the copy holds %s" % (expect, ", ".join(sorted(found)) or "no readable version"))
    files = listed(root)
    missing, wrong = [], []
    if files is None:
        problems.append("integrity: MANIFEST.sha256 is missing, so the copy cannot be checked")
        files = {}
    for rel, digest in sorted(files.items()):
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            missing.append(rel)
        elif sha256_file(p) != digest:
            wrong.append(rel)
    if missing:
        problems.append("integrity: %d file(s) of the manifest are missing, for example %s" % (len(missing), ", ".join(missing[:5])))
    if wrong:
        problems.append("integrity: %d file(s) differ from the manifest, for example %s" % (len(wrong), ", ".join(wrong[:5])))
    for rel in require:
        if not os.path.isfile(os.path.join(root, rel)):
            problems.append("required file missing: %s" % rel)
    extra = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (os.path.abspath(base) == os.path.abspath(root) and d == "deliveries"))
        for n in names:
            rel = os.path.relpath(os.path.join(base, n), root).replace(os.sep, "/")
            if rel not in files and rel != "MANIFEST.sha256" and not rel.endswith(".pyc"):
                extra.append(rel)
    return problems, {"versions": vs, "version": sorted(found)[0] if len(found) == 1 else None, "listed": len(files), "missing": missing, "differing": wrong, "extra": sorted(extra)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set_dir", nargs="?", default=os.path.abspath(os.path.join(HERE, "..")))
    ap.add_argument("--expect", metavar="X.Y.Z", help="the version the copy is said to be")
    ap.add_argument("--require", action="append", default=[], metavar="PATH", help="a file that must exist below SET_DIR (repeatable)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.expect and not re.fullmatch(r"\d+\.\d+\.\d+", a.expect):
        print("ERROR --expect must look like 2.3.0", file=sys.stderr)
        sys.exit(2)
    root = os.path.abspath(a.set_dir)
    if not (os.path.isfile(os.path.join(root, "CHANGELOG.md")) and os.path.isdir(os.path.join(root, "tools"))):
        print("ERROR %s is not a guide set (no CHANGELOG.md and tools/)" % root, file=sys.stderr)
        sys.exit(3)
    problems, details = check(root, a.expect, a.require)
    result = {"tool": "check_set.py", "toolVersion": VERSION, "result": "pass" if not problems else "fail", "problems": problems, **details}
    if a.json:
        print(json.dumps(result, indent=1))
    else:
        print("guide set %s: %s; %d listed file(s), %d missing, %d differing, %d not in the manifest" % (
            details["version"] or "version unclear", "OK" if not problems else "NOT OK", details["listed"], len(details["missing"]), len(details["differing"]), len(details["extra"])))
        for p in problems:
            print("  FAIL " + p)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
