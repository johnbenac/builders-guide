#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check a copy of the guide set that someone has staged somewhere (a packet, a vendored folder, a mirror): is it the version it claims, is it whole, and
does it hold the tools the people who use it were promised?

    python3 tools/check_set.py [SET_DIR] [--expect X.Y.Z] [--require PATH ...] [--strict] [--allow-unreleased] [--json]

SET_DIR is the top folder of the copy (default: the folder this script is in). Checks:
  * version: the newest heading of CHANGELOG.md, `version` of rules.json and MANIFEST.json, and the `VERSION` of every tool agree, and with `--expect`
    equal the stated version (a hand-over note that says "the guide is 2.3.0" and a folder that holds 2.1.0 is the typical fault). A CHANGELOG whose
    top heading is "Unreleased" is a tree that is not a release and fails, unless `--allow-unreleased`;
  * the manifest: MANIFEST.sha256 must be a list of `<64 hex digits>  <path>` lines and nothing else (a blank, truncated, binary-mode or otherwise
    differently formatted file fails, and so does a list of no files), every path must stay inside SET_DIR (no absolute path, no `..`, no symbolic
    link), and its rows must be the files of MANIFEST.json (plus MANIFEST.json itself and the documents in dist/) with the same hashes, so that a file
    cannot be removed or changed in one list only;
  * integrity: every file in MANIFEST.sha256 exists and has the listed hash (a missing tool, a hand-edited tool, a half-copied folder). The documents
    in dist/ are exempt from "missing" because a staged copy may leave them out; when they are there they must have the listed hash and the version
    of the set;
  * dist/: when `dist/` holds the zip, its members must be exactly the files of the manifest (plus MANIFEST.sha256) with the listed hashes, and
    dist/SHA256SUMS.txt and the zip's `.sha256` file must agree with the files they name that are present;
  * `--require PATH` (repeatable, a path below SET_DIR such as tools/export_glb.py): the file exists. For a set that carries its own tools folder
    nothing else needs to be named: a copy that passes the integrity check holds every tool the manifest lists.
Files of the set that are not in the manifest (a program added to tools/, a changed guide whose row was not added) are named in the output and in
`extra`; they fail with `--strict`. What `tools/fileset.py` leaves out of the set (dist/, work/, deliveries/, caches, folders and top-level files
that start with a dot) is not looked at.

Exit codes: 0 the copy is what it says and is whole, 1 at least one check failed (an unreadable file is a failed check, not a crash), 2 wrong command
line, 3 SET_DIR is not a guide set or the check itself broke.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fileset  # noqa: E402

VERSION = "2.3.0"
ROW = re.compile(r"^([0-9a-f]{64})  (\S.*)$")
DIST_DOC = re.compile(r"^dist/builders-guide-(\d+\.\d+\.\d+)\.(html|pdf)$")
TOOL_VERSION = re.compile(r'^(?:TOOL_)?VERSION = "(\d+\.\d+\.\d+)"', re.M)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def changelog_head(root):
    """(version of the top heading or None, text of the top heading, version of the newest numbered heading or None, problem or None)."""
    try:
        text = read_text(os.path.join(root, "CHANGELOG.md"))
    except (OSError, UnicodeDecodeError) as exc:
        return None, None, None, "CHANGELOG.md cannot be read (%s)" % type(exc).__name__
    heads = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
    if not heads:
        return None, None, None, "CHANGELOG.md has no version heading"
    nums = [m.group(1) for m in (re.match(r"(\d+\.\d+\.\d+)\b", h) for h in heads) if m]
    top = re.match(r"(\d+\.\d+\.\d+)\b", heads[0])
    return (top.group(1) if top else None), heads[0], (nums[0] if nums else None), None


def versions(root, allow_unreleased=False):
    """({where: version string or None}, [problem]) for every place a version is stated."""
    out, problems = {}, []
    top, head, newest, prob = changelog_head(root)
    if prob:
        problems.append("version: " + prob)
        out["CHANGELOG.md"] = None
    elif top is None and re.match(r"unreleased\b", head or "", re.I):
        if not allow_unreleased:
            problems.append("version: the top heading of CHANGELOG.md is %r: this tree is not a release (the files may differ from the version they name)" % head)
        out["CHANGELOG.md"] = newest
    else:
        out["CHANGELOG.md"] = top
    for name in ("rules.json", "MANIFEST.json"):
        try:
            out[name] = str(json.loads(read_text(os.path.join(root, name))).get("version"))
        except (OSError, ValueError, UnicodeDecodeError, AttributeError):
            out[name] = None
    tdir = os.path.join(root, "tools")
    if os.path.isdir(tdir):
        for fn in sorted(os.listdir(tdir)):
            if fn.endswith(".py"):
                try:
                    m = TOOL_VERSION.search(read_text(os.path.join(tdir, fn)))
                except (OSError, UnicodeDecodeError):
                    out["tools/" + fn] = None
                    problems.append("version: tools/%s cannot be read" % fn)
                    continue
                if m:
                    out["tools/" + fn] = m.group(1)
    return out, problems


def unsafe_path(rel):
    """Why a manifest path may not be used, or None."""
    parts = rel.split("/")
    if rel.startswith("/") or "\\" in rel or re.match(r"^[A-Za-z]:", rel) or any(p in ("", ".", "..") for p in parts) or "\0" in rel:
        return "is not a path inside the set"
    return None


def listed(root):
    """({path: sha256}, [problem]) of MANIFEST.sha256. A file that is missing, empty, or has a line that is not `<64 hex>  <path>` is a problem."""
    problems = []
    try:
        text = read_text(os.path.join(root, "MANIFEST.sha256"))
    except OSError:
        return None, ["integrity: MANIFEST.sha256 is missing, so the copy cannot be checked"]
    except UnicodeDecodeError:
        return None, ["integrity: MANIFEST.sha256 is not text"]
    out = {}
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    else:
        problems.append("integrity: MANIFEST.sha256 does not end with a newline (truncated?)")
    for n, line in enumerate(lines, 1):
        m = ROW.match(line)
        if not m:
            if len(problems) < 5:
                problems.append("integrity: MANIFEST.sha256 line %d is not '<64 hex digits>  <path>': %r" % (n, line[:60]))
            continue
        rel = m.group(2)
        why = unsafe_path(rel)
        if why:
            problems.append("integrity: MANIFEST.sha256 line %d: %r %s" % (n, rel[:60], why))
        elif rel in out:
            problems.append("integrity: MANIFEST.sha256 lists %s twice" % rel)
        else:
            out[rel] = m.group(1)
    if not out:
        problems.append("integrity: MANIFEST.sha256 lists no files")
    return out, problems


def manifest_json(root):
    """({path: sha256} of the `files` array of MANIFEST.json, problem or None)."""
    try:
        d = json.loads(read_text(os.path.join(root, "MANIFEST.json")))
        return {f["path"]: f["sha256"] for f in d["files"]}, None
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None, "integrity: MANIFEST.json cannot be read as a list of files with hashes"


def inside(root, rel):
    """The path of a manifest row if it is a regular file below root (not a symbolic link, not through one), else None."""
    full = os.path.join(root, *rel.split("/"))
    if os.path.islink(full):
        return None
    rr = os.path.realpath(root)
    rp = os.path.realpath(full)
    return full if rp == rr or rp.startswith(rr + os.sep) else None


def check_dist(root, files, version, problems, details):
    """The documents, checksums and zip in dist/ against the manifest. Only what is there is checked."""
    d = os.path.join(root, "dist")
    if not os.path.isdir(d):
        details["dist"] = None
        return
    present = sorted(os.listdir(d))
    info = {"files": present}
    details["dist"] = info
    for n in present:
        m = re.match(r"^builders-guide-(\d+\.\d+\.\d+)\.(html|pdf|zip|zip\.sha256)$", n)
        if m and version and m.group(1) != version:
            problems.append("dist: %s is of version %s, the set is %s (a stale hand-over file)" % (n, m.group(1), version))
    for rel in fileset.dist_files(root):
        if rel not in files:
            problems.append("dist: %s is not in MANIFEST.sha256" % rel)
    # the checksum files agree with the files they name that are present
    for sumfile in [n for n in present if n == "SHA256SUMS.txt" or n.endswith(".zip.sha256")]:
        try:
            lines = [ln for ln in read_text(os.path.join(d, sumfile)).splitlines() if ln.strip()]
        except (OSError, UnicodeDecodeError):
            problems.append("dist: %s cannot be read" % sumfile)
            continue
        for ln in lines:
            m = ROW.match(ln)
            if not m or "/" in m.group(2):
                problems.append("dist: %s has a line that is not '<64 hex digits>  <file>': %r" % (sumfile, ln[:60]))
                continue
            p = os.path.join(d, m.group(2))
            if os.path.isfile(p) and not os.path.islink(p) and sha256_file(p) != m.group(1):
                problems.append("dist: %s says %s has another hash than the file" % (sumfile, m.group(2)))
    zips = [n for n in present if n.endswith(".zip")]
    for zn in zips:
        info["zip"] = zn
        try:
            with zipfile.ZipFile(os.path.join(d, zn)) as z:
                members = {}
                for zi in z.infolist():
                    if zi.is_dir():
                        continue
                    top, _, rel = zi.filename.partition("/")
                    if top != zn[:-4] or not rel or unsafe_path(rel):
                        problems.append("dist: %s holds the member %r, which is not below %s/" % (zn, zi.filename[:60], zn[:-4]))
                        continue
                    members[rel] = hashlib.sha256(z.read(zi)).hexdigest()
        except (zipfile.BadZipFile, OSError, RuntimeError, EOFError) as exc:
            problems.append("dist: %s cannot be read as a zip (%s)" % (zn, type(exc).__name__))
            continue
        expected = dict(files)
        try:
            expected["MANIFEST.sha256"] = sha256_file(os.path.join(root, "MANIFEST.sha256"))
        except OSError:
            pass
        missing = sorted(set(expected) - set(members))
        extra = sorted(set(members) - set(expected))
        wrong = sorted(k for k in set(members) & set(expected) if members[k] != expected[k])
        if missing:
            problems.append("dist: %s lacks %d file(s) of the manifest, for example %s" % (zn, len(missing), ", ".join(missing[:5])))
        if extra:
            problems.append("dist: %s holds %d file(s) that are not in the manifest, for example %s" % (zn, len(extra), ", ".join(extra[:5])))
        if wrong:
            problems.append("dist: %s holds %d file(s) that differ from the manifest, for example %s" % (zn, len(wrong), ", ".join(wrong[:5])))


def check(root, expect=None, require=(), strict=False, allow_unreleased=False, dist=True):
    """(problems, details): problems is a list of strings; details has the versions, counts and extra files."""
    vs, problems = versions(root, allow_unreleased)
    found = {v for v in vs.values() if v}
    if None in vs.values():
        problems.append("version: not readable in %s" % ", ".join(k for k, v in vs.items() if v is None))
    if len(found) > 1:
        top = vs.get("CHANGELOG.md")
        problems.append("version: the files disagree; CHANGELOG.md says %s but %s" % (top, ", ".join("%s says %s" % (k, v) for k, v in sorted(vs.items()) if v and v != top)[:300]))
    if expect and found != {expect}:
        problems.append("version: expected %s, the copy holds %s" % (expect, ", ".join(sorted(found)) or "no readable version"))
    version = sorted(found)[0] if len(found) == 1 else None
    files, prob = listed(root)
    problems += prob
    files = files or {}
    missing, wrong, unreadable, escaping = [], [], [], []
    for rel, digest in sorted(files.items()):
        p = inside(root, rel)
        if p is None:
            if os.path.lexists(os.path.join(root, *rel.split("/"))):
                escaping.append(rel)
            elif not rel.startswith("dist/"):
                missing.append(rel)
            continue
        if not os.path.isfile(p):
            if not rel.startswith("dist/"):    # the hand-over documents may be left out of a staged copy (they are tracked in the repository, a copy need not carry them)
                missing.append(rel)
            continue
        try:
            if sha256_file(p) != digest:
                wrong.append(rel)
        except OSError:
            unreadable.append(rel)
    if escaping:
        problems.append("integrity: %d manifest path(s) are symbolic links or lead outside the set, for example %s" % (len(escaping), ", ".join(escaping[:5])))
    if unreadable:
        problems.append("integrity: %d file(s) cannot be read, for example %s" % (len(unreadable), ", ".join(unreadable[:5])))
    if missing:
        problems.append("integrity: %d file(s) of the manifest are missing, for example %s" % (len(missing), ", ".join(missing[:5])))
    if wrong:
        problems.append("integrity: %d file(s) differ from the manifest, for example %s" % (len(wrong), ", ".join(wrong[:5])))
    # the two lists agree: no file can be dropped or replaced in one of them only
    mj, prob = manifest_json(root)
    if prob:
        problems.append(prob)
    elif files:
        core = {k: v for k, v in files.items() if not k.startswith("dist/")}
        want = set(mj) | {"MANIFEST.json"}
        only_sha = sorted(set(core) - want)
        only_json = sorted(want - set(core))
        differ = sorted(k for k in set(core) & set(mj) if core[k] != mj[k])
        if only_sha:
            problems.append("integrity: MANIFEST.sha256 lists %d file(s) that MANIFEST.json does not, for example %s" % (len(only_sha), ", ".join(only_sha[:5])))
        if only_json:
            problems.append("integrity: MANIFEST.json lists %d file(s) that MANIFEST.sha256 does not, for example %s" % (len(only_json), ", ".join(only_json[:5])))
        if differ:
            problems.append("integrity: MANIFEST.json and MANIFEST.sha256 give different hashes for %d file(s), for example %s" % (len(differ), ", ".join(differ[:5])))
    for rel in require:
        if unsafe_path(rel) or inside(root, rel) is None or not os.path.isfile(os.path.join(root, *rel.split("/"))):
            problems.append("required file missing: %s" % rel)
    details = {"dist": None}
    if dist and files:
        check_dist(root, files, version, problems, details)
    extra = sorted(set(fileset.set_files(root)) - set(files) - {fileset.CHECKSUM_FILE})
    if extra and strict:
        problems.append("extra: %d file(s) are not in the manifest, for example %s" % (len(extra), ", ".join(extra[:5])))
    details.update({"versions": vs, "version": version, "listed": len(files), "missing": missing, "differing": wrong, "extra": extra})
    return problems, details


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set_dir", nargs="?", default=os.path.abspath(os.path.join(HERE, "..")))
    ap.add_argument("--expect", metavar="X.Y.Z", help="the version the copy is said to be")
    ap.add_argument("--require", action="append", default=[], metavar="PATH", help="a file that must exist below SET_DIR (repeatable)")
    ap.add_argument("--strict", action="store_true", help="files of the set that are not in the manifest fail the check")
    ap.add_argument("--allow-unreleased", action="store_true", help="a CHANGELOG whose top heading is Unreleased is accepted (a tree under development)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.expect and not re.fullmatch(r"\d+\.\d+\.\d+", a.expect):
        print("ERROR --expect must look like 2.3.0", file=sys.stderr)
        sys.exit(2)
    root = os.path.abspath(a.set_dir)
    if not (os.path.isfile(os.path.join(root, "CHANGELOG.md")) and os.path.isdir(os.path.join(root, "tools"))):
        print("ERROR %s is not a guide set (no CHANGELOG.md and tools/)" % root, file=sys.stderr)
        sys.exit(3)
    try:
        problems, details = check(root, a.expect, a.require, a.strict, a.allow_unreleased)
    except Exception as exc:                 # a defect of the check or something it cannot read: an exit code, never a traceback, and JSON for a consumer of --json
        msg = "the check itself failed: %s: %s" % (type(exc).__name__, str(exc)[:160])
        if a.json:
            print(json.dumps({"tool": "check_set.py", "toolVersion": VERSION, "result": "error", "problems": [msg]}, indent=1))
        else:
            print("ERROR " + msg, file=sys.stderr)
        sys.exit(3)
    result = {"tool": "check_set.py", "toolVersion": VERSION, "result": "pass" if not problems else "fail", "problems": problems, **details}
    if a.json:
        print(json.dumps(result, indent=1))
    else:
        print("guide set %s: %s; %d listed file(s), %d missing, %d differing, %d not in the manifest" % (
            details["version"] or "version unclear", "OK" if not problems else "NOT OK", details["listed"], len(details["missing"]), len(details["differing"]), len(details["extra"])))
        for p in problems:
            print("  FAIL " + p)
        if details["extra"]:
            print("  not in the manifest (%s):" % ("fails with --strict" if not a.strict else "failed"))
            for n in details["extra"][:20]:
                print("    " + n)
            if len(details["extra"]) > 20:
                print("    ... and %d more (--json lists all)" % (len(details["extra"]) - 20))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
