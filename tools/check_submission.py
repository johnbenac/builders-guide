#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Checks the form of a submitted delivery folder (guide 4, section 8): layout, limits, allowed file types, safe paths, licence.

    python3 tools/check_submission.py DELIVERY_DIR [--profile PROFILE.json] [--json] [--out REPORT.json]

DELIVERY_DIR is deliveries/<slug>/. The checks look only at names, sizes, modes and the first bytes of files; nothing in the delivery is
run, imported or unpacked. The limits are the `submission` group of the profile. Rules X-70 to X-78 (rules.json). Exit codes as in
report.py: 0 no REQUIRED rule failed, 1 at least one did, 2 wrong command line, 3 the folder could not be read.
"""
import argparse
import json
import os
import re
import stat
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report as rpt  # noqa: E402

VERSION = "2.2.0"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_CHARS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RESERVED = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}
ACTIVE = re.compile(rb"<\s*(script|iframe|object|embed)\b", re.I)
PNG = b"\x89PNG\r\n\x1a\n"


def walk(root):
    """(relative path, lstat result) of every entry below root, sorted; never follows a link."""
    out = []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs.sort()
        for n in sorted(names + list(dirs)):
            full = os.path.join(base, n)
            out.append((os.path.relpath(full, root).replace(os.sep, "/"), os.lstat(full)))
    return sorted(out)


def safe_rel(p):
    """Why a relative path string is unsafe, or None."""
    if not isinstance(p, str) or not p:
        return "empty path"
    if p.startswith("/") or "\\" in p or re.match(r"^[A-Za-z]:", p) or "\0" in p:
        return "absolute or non-portable path %r" % p[:60]
    parts = p.split("/")
    if any(x in ("", ".", "..") for x in parts):
        return "path with an empty, '.' or '..' part: %r" % p[:60]
    return None


def image_pixels(head, ext):
    if ext == "png" and head[:8] == PNG and len(head) >= 24:
        return int.from_bytes(head[16:20], "big") * int.from_bytes(head[20:24], "big")
    if ext == "jpg":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                return None
            mk = head[i + 1]
            if mk in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                return int.from_bytes(head[i + 5:i + 7], "big") * int.from_bytes(head[i + 7:i + 9], "big")
            i += 2 + int.from_bytes(head[i + 2:i + 4], "big")
    return None


def check(root):
    P = lambda k, d=None: rpt.param("submission." + k, d)  # noqa: E731
    F = []
    add = lambda rule, ok, msg, **kw: F.append(rpt.finding(  # noqa: E731
        rule, "pass" if ok else ("fail" if rpt.level_of(rule) == "REQUIRED" else "warn"), msg, **kw))
    slug = os.path.basename(os.path.abspath(root))
    entries = walk(root)
    files = [(r, st) for r, st in entries if stat.S_ISREG(st.st_mode)]

    # X-75 links and special files first: everything below assumes plain files and folders
    odd = [r for r, st in entries if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode))]
    add("X-75", not odd, "only plain files and folders" if not odd else "%d symbolic link(s) or special file(s), first: %s" % (len(odd), odd[0]),
        element=odd[0] if odd else None)

    # X-74 path safety
    probs = []
    seen, seen_dirs = {}, {}
    for r, st in entries:
        why = safe_rel(r)
        if why:
            probs.append(why)
            continue
        for part in r.split("/"):
            if not NAME_CHARS.match(part) or len(part) > 100:
                probs.append("file name not portable (letters, digits, dot, hyphen, underscore; not starting with a dot): %r" % r)
                break
            if part.split(".")[0].lower() in RESERVED:
                probs.append("reserved device name in %r" % r)
                break
        if len(r) > P("maxPathLength", 200):
            probs.append("path longer than %d characters: %s" % (P("maxPathLength", 200), r[:60]))
        key = unicodedata.normalize("NFC", r).casefold()
        if key in seen and seen[key] != r:
            probs.append("names differ only by case or accents: %s and %s" % (seen[key], r))
        seen[key] = r
    # paths named inside the manifest and the checksum list must be safe too
    man, mpath = None, os.path.join(root, "delivery.json")
    if os.path.isfile(mpath) and not os.path.islink(mpath):
        try:
            with open(mpath, encoding="utf-8") as fh:
                man = json.load(fh)
        except (ValueError, OSError, RecursionError, UnicodeDecodeError):
            man = None
    named = [f.get("path") for f in (man or {}).get("files", []) if isinstance(f, dict)] if isinstance((man or {}).get("files"), list) else []
    sums = os.path.join(root, "SHA256SUMS.txt")
    if os.path.isfile(sums) and not os.path.islink(sums):
        try:
            with open(sums, encoding="utf-8") as fh:
                named += [ln.rstrip("\n").partition("  ")[2] for ln in fh if ln.strip()][:5000]
        except (OSError, UnicodeDecodeError):
            pass
    for p in named:
        why = safe_rel(p)
        if why:
            probs.append("manifest or checksum list: " + why)
    add("X-74", not probs, "all paths are relative, portable and unique" if not probs else "%d unsafe path(s), first: %s" % (len(probs), probs[0]),
        element=probs[0][:80] if probs else None)

    # X-72 allowed file types
    allowed = {e.lower().lstrip(".") for e in P("allowedExtensions", [])}
    bad_ext = [r for r, st in files if r.rsplit(".", 1)[-1].lower() not in allowed or "." not in r.rsplit("/", 1)[-1]]
    execbit = [r for r, st in files if st.st_mode & 0o111]
    add("X-72", not bad_ext and not execbit,
        "every file has an allowed type and none is executable" if not (bad_ext or execbit) else
        ("%d file(s) of a type that is not allowed (%s), first: %s" % (len(bad_ext), ", ".join(sorted(allowed)), bad_ext[0]) if bad_ext else
         "%d file(s) with the executable bit set, first: %s" % (len(execbit), execbit[0])), element=(bad_ext or execbit or [None])[0])

    # X-73 counts and sizes
    total = sum(st.st_size for _, st in files)
    big = [r for r, st in files if st.st_size > P("maxFileBytes", 26214400)]
    why = []
    if len(files) > P("maxFiles", 200):
        why.append("%d files (limit %d)" % (len(files), P("maxFiles", 200)))
    if total > P("maxDeliveryBytes", 104857600):
        why.append("%d bytes in total (limit %d)" % (total, P("maxDeliveryBytes", 104857600)))
    if big:
        why.append("%d file(s) over %d bytes, first: %s" % (len(big), P("maxFileBytes", 26214400), big[0]))
    add("X-73", not why, "%d files, %d bytes: within the limits" % (len(files), total) if not why else "; ".join(why), element=big[0] if big else None)

    # X-77 a file is what its name says
    mism = []
    maxpx = P("maxImagePixels", 67108864)
    for r, st in files:
        ext = r.rsplit(".", 1)[-1].lower()
        if ext not in allowed or st.st_size > P("maxFileBytes", 26214400):
            continue
        try:
            with open(os.path.join(root, r), "rb") as fh:
                head = fh.read(65536 if ext == "jpg" else 4096)
                body = None
                if ext in ("json", "md", "txt", "csv"):
                    body = head + fh.read()
        except OSError as exc:
            mism.append("%s: cannot read (%s)" % (r, exc))
            continue
        if ext == "png" and head[:8] != PNG:
            mism.append("%s is not a PNG image" % r)
        elif ext == "jpg" and head[:3] != b"\xff\xd8\xff":
            mism.append("%s is not a JPEG image" % r)
        elif ext == "glb" and not (head[:4] == b"glTF" and int.from_bytes(head[4:8], "little") == 2 and int.from_bytes(head[8:12], "little") == st.st_size):
            mism.append("%s is not a binary glTF 2 file of the stated length" % r)
        elif ext == "ifc" and not (b"HEADER;" in head[:512] and b"FILE_SCHEMA" in head and b"\0" not in head):
            mism.append("%s does not look like an IFC text file" % r)
        elif ext in ("png", "jpg"):
            px = image_pixels(head, ext)
            if px is None and ext == "png":
                mism.append("%s has no readable PNG header" % r)
            elif px is not None and px > maxpx:
                mism.append("%s has %d pixels (limit %d)" % (r, px, maxpx))
        elif body is not None:
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                mism.append("%s is not UTF-8 text" % r)
                continue
            if "\0" in text or ACTIVE.search(body):
                mism.append("%s contains a NUL byte or active markup (script, iframe, object, embed)" % r)
            elif ext == "json":
                try:
                    json.loads(text)
                except (ValueError, RecursionError):
                    mism.append("%s is not valid JSON" % r)
    add("X-77", not mism, "file contents match their file types" if not mism else "%d file(s) are not what their name says, first: %s" % (len(mism), mism[0]),
        element=mism[0].split(" ")[0] if mism else None)

    # X-70 layout and submission block
    p70 = []
    if not SLUG.match(slug) or len(slug) > 60:
        p70.append("folder name %r is not a slug (lower-case letters, digits, single hyphens, at most 60 characters)" % slug)
    if man is None:
        p70.append("no readable delivery.json at the top of the delivery")
    else:
        did = (man.get("delivery") or {}).get("id") if isinstance(man.get("delivery"), dict) else None
        if did != slug:
            p70.append("delivery.id %r must equal the folder name %r" % (did, slug))
        if not isinstance(man.get("submission"), dict):
            p70.append("delivery.json has no submission block")
        else:
            try:
                import jsonschema
                with open(os.path.join(rpt.ROOT, "schemas", "submission.schema.json"), encoding="utf-8") as fh:
                    sch = json.load(fh)
                for e in sorted(jsonschema.Draft7Validator(sch).iter_errors(man["submission"]), key=lambda e: list(e.path))[:6]:
                    p70.append("submission: %s: %s" % ("/".join(map(str, e.path)) or "(top)", e.message[:140]))
            except ImportError:
                p70.append("jsonschema is not installed; the submission block could not be validated")
    add("X-70", not p70, "folder name, delivery.id and the submission block are in order" if not p70 else p70[0], file="delivery.json")

    # X-71 licence, X-76 attestation
    sub = (man or {}).get("submission") if isinstance((man or {}).get("submission"), dict) else {}
    lic, okl = sub.get("licence"), P("allowedLicences", [])
    add("X-71", lic in okl, "licence %s is one the profile takes" % lic if lic in okl else "licence %r is not one of: %s" % (lic, ", ".join(okl)), file="delivery.json")
    att = sub.get("attestation") if isinstance(sub.get("attestation"), dict) else {}
    miss = [k for k in ("ownWork", "mayLicense", "noRestrictedContent") if att.get(k) is not True]
    add("X-76", not miss, "the submitter attests ownership, the right to license and no restricted content" if not miss else "attestation not made: %s" % ", ".join(miss), file="delivery.json")

    # X-78 previews
    prev = [r for r, _ in files if re.match(r"^(previews/[^/]+|items/[^/]+/preview)\.(png|jpg)$", r)]
    F.append(rpt.finding("X-78", "pass" if prev else "warn", "%d preview image(s)" % len(prev) if prev else "no preview image under previews/ or items/<id>/preview.png"))
    return rpt.make_report("check_submission.py", VERSION, {"path": slug}, F, counts={"files": len(files), "bytes": total})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("delivery")
    ap.add_argument("--profile")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    rpt.load_profile(a.profile)
    if not os.path.isdir(a.delivery) or os.path.islink(a.delivery):
        rep = rpt.make_report("check_submission.py", VERSION, {"path": a.delivery}, [], error="not a folder: %s" % a.delivery)
    else:
        rep = check(a.delivery)
    if a.out:
        rpt.write(rep, a.out)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for line in rpt.text_lines(rep):
            print(line)
        s = rep["summary"]
        print("submission: %s (%d REQUIRED failure(s), %d RECOMMENDED warning(s))" % (rep["result"].upper(), s["requiredFailures"], s["recommendedWarnings"]))
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    main()
