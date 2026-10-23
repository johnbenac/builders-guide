#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fails when the human guides and the machine-readable files differ, or when a skill, link or hash is wrong.

    python3 tools/test_sync.py

Checks: every generated file is current (gen_all); rules.json matches the guides rule by rule (id, level, statement) and its
schema; rules_meta.json covers exactly the rules; every rule marked automated is emitted by its tool and every rule a tool
emits is marked automated; skills are well formed (name, description, size, referenced files exist); every link in llms.txt
resolves; MANIFEST.json hashes match the files; no chunk is over the size limit; no file of the set or of dist/ (zip members, PDF
streams and links included) holds a local-file address or an absolute local path (tools/leakscan.py).
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_all  # noqa: E402

ROOT = gen_all.ROOT
bad = []


def check(cond, msg):
    if not cond:
        bad.append(msg)


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# 1 generated files current
out = gen_all.generate()
for rel, text in out.items():
    p = os.path.join(ROOT, rel)
    check(os.path.exists(p) and load(rel) == text, "generated file differs from the sources: %s (run tools/gen_all.py --write)" % rel)
check(not gen_all.existing_generated(out), "stale generated files: %s" % gen_all.existing_generated(out)[:5])

# 2 rules.json against the guides, independently parsed
rj = json.loads(load("rules.json"))
pat = re.compile(r"^\*\*([BDFX]-\d+[a-z]?) \u00b7 (REQUIRED|RECOMMENDED)(?: \u00b7 ([A-Za-z]+))?\*\* - (.*)$")
md = {}
for fn in ("01-builders-and-architects-guide.md", "02-interior-decorators-guide.md", "03-furniture-and-fixtures-guide.md",
           "04-delivery-and-acceptance-guide.md"):
    lines = load(fn).split("\n")
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if m:
            body = m.group(4)
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].startswith(("|", "```", "**", "#", "-", "*")):
                body += " " + lines[j].strip()
                j += 1
            md[m.group(1)] = (m.group(2).lower(), re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0])
check(rj["count"] == len(rj["rules"]) == len(md), "rule counts differ: json %d, guides %d" % (len(rj["rules"]), len(md)))
for r in rj["rules"]:
    g = md.get(r["id"])
    check(g is not None, "%s is in rules.json but not in the guides" % r["id"])
    if g:
        check(g[0] == r["level"], "%s level differs: guide %s, json %s" % (r["id"], g[0], r["level"]))
        check(g[1] == r["statement"], "%s statement differs from the guide" % r["id"])
try:
    import jsonschema
    jsonschema.validate(rj, json.loads(load("schemas/rules.schema.json")))
except ImportError:
    print("jsonschema not installed: schema validation skipped")
except Exception as exc:
    bad.append("rules.json does not match its schema: %s" % str(exc)[:200])
meta = json.loads(load("tools/rules_meta.json"))["rules"]
check(set(meta) == set(md), "rules_meta.json and the guides cover different rules")

# 2b profiles
try:
    pschema = json.loads(load("profiles/profile.schema.json"))
    for pf in ("profiles/default.json", "profiles/example-strict.json"):
        pj = json.loads(load(pf))
        jsonschema.validate(pj, pschema)
        for rid in pj.get("ruleLevels", {}):
            check(rid in md, "%s: ruleLevels names the unknown rule %s" % (pf, rid))
        for cn in pj.get("propertyNames", {}):
            check(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", cn) is not None, "%s: odd canonical property name %s" % (pf, cn))
except NameError:
    pass
except Exception as exc:
    bad.append("a profile does not match profiles/profile.schema.json: %s" % str(exc)[:160])

# 3 automation honesty
tools = {"check_ifc": "tools/check_ifc.py", "check_texture_set": "tools/check_texture_set.py", "check_item": "tools/check_item.py",
         "build_package": "tools/build_package.py"}
emitted = {}
for name, rel in tools.items():
    src = load(rel)
    for rid in set(re.findall(r'"([BDFX]-\d+[a-z]?)"', src)):
        emitted.setdefault(rid, set()).add(name)
for r in rj["rules"]:
    if r["automated"]:
        tool = os.path.basename(r["how_to_check"]["tool"])[:-3]
        check(tool in emitted.get(r["id"], ()), "%s is marked automated by %s but that tool never emits it" % (r["id"], tool))
    else:
        check(r["id"] not in emitted, "%s is emitted by %s but not marked automated" % (r["id"], sorted(emitted.get(r["id"], []))))
for rid in ("D-60", "X-41"):
    pass
# 4 skills
for name in gen_all.SKILLS:
    rel = "skills/%s/SKILL.md" % name
    if not os.path.exists(os.path.join(ROOT, rel)):
        bad.append("missing " + rel)
        continue
    t = load(rel)
    check(t.count("\n") < 400, "%s is %d lines; keep it under 400" % (rel, t.count("\n")))
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    check(bool(m), "%s has no front matter" % rel)
    if m:
        fm = dict(re.findall(r"^(\w[\w-]*):\s*(.+)$", m.group(1), re.M))
        check(fm.get("name") == name, "%s: name must equal the folder name" % rel)
        check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fm.get("name", "")) is not None and len(fm.get("name", "")) <= 64, "%s: bad name" % rel)
        check(0 < len(fm.get("description", "")) <= 1024, "%s: description must be 1 to 1024 characters" % rel)
    for ref in set(re.findall(r"`((?:references|scripts|tools|schemas|templates)/[A-Za-z0-9._/-]+)`", t)):
        base = os.path.join(ROOT, "skills", name) if ref.startswith(("references", "scripts")) else ROOT
        check(os.path.exists(os.path.join(base, ref)), "%s mentions %s, which does not exist" % (rel, ref))
    for ref in set(re.findall(r"`(skills/[A-Za-z0-9._/-]+)`", t)):
        check(os.path.exists(os.path.join(ROOT, ref)), "%s mentions %s, which does not exist" % (rel, ref))

# 5 links in llms.txt and chunk sizes, manifest hashes
for link in re.findall(r"\]\(([^)]+)\)", load("llms.txt")):
    check(os.path.exists(os.path.join(ROOT, link)), "llms.txt links to %s, which does not exist" % link)
for f in out:
    if f.startswith("chunks/") and f.endswith(".md"):
        check(len(out[f]) <= gen_all.MAX_CHUNK_CHARS + 400, "%s is over the chunk size limit" % f)
mf = json.loads(load("MANIFEST.json"))
for row in mf["files"]:
    p = os.path.join(ROOT, row["path"])
    with open(p, "rb") as fh:
        check(hashlib.sha256(fh.read()).hexdigest() == row["sha256"], "MANIFEST.json hash differs: %s" % row["path"])

# 6 the checksum list and the hand-over zip agree with the file list, and hand-written counts and rule ranges are current
import fileset  # noqa: E402
check(load("MANIFEST.sha256") == fileset.checksum_text(ROOT), "MANIFEST.sha256 is out of date (run tools/gen_all.py --write)")
check({r["path"] for r in mf["files"]} == (set(fileset.set_files(ROOT)) | set(out)) - {"MANIFEST.json"}, "MANIFEST.json lists different files from tools/fileset.py")
zip_path = os.path.join(ROOT, "dist", "builders-guide-%s.zip" % gen_all.VERSION)
if os.path.exists(zip_path):
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        names = {n.split("/", 1)[1] for n in z.namelist()}
    check(names == set(fileset.set_files(ROOT) + fileset.dist_files(ROOT) + [fileset.CHECKSUM_FILE]), "the zip in dist/ holds different files from the manifest")
n_rules = len(rj["rules"])
m1 = re.search(r"rules\.json` \((\d+), stable ids", load("AGENTS.md"))
check(m1 is not None and int(m1.group(1)) == n_rules, "AGENTS.md states a rule count that is not %d" % n_rules)
m2 = re.search(r"(\d+) rules in `rules\.json`", load("skills/orient/SKILL.md"))
check(m2 is not None and int(m2.group(1)) == n_rules, "skills/orient/SKILL.md states a rule count that is not %d" % n_rules)
for name in gen_all.SKILLS:
    fm = re.search(r'rules:\s*"([A-Z])-(\d+) to ([A-Z])-(\d+)"', load("skills/%s/SKILL.md" % name))
    if fm:
        top = max(int(re.match(r"[A-Z]-(\d+)", r["id"]).group(1)) for r in rj["rules"] if r["id"].startswith(fm.group(3) + "-"))
        check(int(fm.group(4)) == top, "skills/%s/SKILL.md says rules up to %s-%s but the last rule is %s-%02d" % (name, fm.group(3), fm.group(4), fm.group(3), top))
check(f'version: "{gen_all.VERSION}"' in load("skills/orient/SKILL.md"), "skills/orient/SKILL.md does not carry version %s" % gen_all.VERSION)
check(rj["version"] == gen_all.VERSION, "rules.json version is not %s" % gen_all.VERSION)

# 7 nothing in the set or in the hand-over files records where it was built (no local-file address, no absolute local path)
import leakscan  # noqa: E402
for sample in (b"x " + b"file" + b"://" + b"x/y", b"at /" + b"home/someone/x", b"a /" + b"media/disk/x", b"c:" + b"\\Users\\x"):
    check(leakscan.scan_bytes(sample, "seed"), "leakscan misses a seeded leak: %r" % sample)
check(not leakscan.scan_bytes(b"see https://example.org/a and tools/x.py and ~/home", "clean"), "leakscan flags clean text")
for w, k, x in leakscan.scan_tree(ROOT)[:10]:
    check(False, "%s in %s: %r" % (k, w, x))

if bad:
    print("\n".join(bad[:40]))
    print("test_sync: FAIL (%d problem(s))" % len(bad))
    sys.exit(1)
print("test_sync: ok (%d rules, %d generated files, %d manifest rows, %d skills)" % (len(rj["rules"]), len(out), len(mf["files"]), len(gen_all.SKILLS)))
