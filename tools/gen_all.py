#!/usr/bin/env python3
"""Generate every machine-readable artifact of the set from the human guides and tools/rules_meta.json.

    python3 tools/gen_all.py --write     write the generated files and MANIFEST.sha256
    python3 tools/gen_all.py --check     fail (exit 1) if any generated file on disk differs from what would be generated

With neither option it only prints this text (exit 2); it never writes by accident.
Generated: 06-rules-index.md, rules.json, chunks/*, llms.txt, llms-full.txt, skills/*/references/*, MANIFEST.json, MANIFEST.sha256.
Hand-written and never touched: the guides, AGENTS.md, REPAIR-LOOP.md, skills/*/SKILL.md, skills/*/scripts/*.
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fileset  # noqa: E402
import rules_index  # noqa: E402

ROOT = rules_index.ROOT = os.path.abspath(os.path.join(HERE, ".."))
VERSION = "2.4.0"
MAX_CHUNK_CHARS = 6000          # about 1,500 tokens
DOCS = [("readme", "README.md"), ("about", "ABOUT.md"), ("g1", "01-builders-and-architects-guide.md"), ("g2", "02-interior-decorators-guide.md"),
        ("g3", "03-furniture-and-fixtures-guide.md"), ("g4", "04-delivery-and-acceptance-guide.md"),
        ("g5", "05-worked-example.md"), ("params", "07-profile-parameters.md"), ("sub", "08-submissions-and-ingest.md"), ("repair", "REPAIR-LOOP.md")]
TOOL_CMD = {
    "check_ifc": "python3 tools/check_ifc.py MASTER.ifc --profile PROFILE.json --finish-schedule finishes/finish-schedule.json --json",
    "check_texture_set": "python3 tools/check_texture_set.py SET_DIR --profile PROFILE.json --json",
    "check_item": "python3 tools/check_item.py ITEM_DIR --profile PROFILE.json --json",
    "build_package": "python3 tools/build_package.py verify PACKAGE_DIR --profile PROFILE.json --json",
    "check_submission": "python3 tools/check_submission.py deliveries/SLUG --profile PROFILE.json --json",
    "validate_glb": "python3 tools/validate_glb.py deliveries/SLUG/proofs/glb --profile PROFILE.json --json",
    "check_proofs": "python3 tools/check_proofs.py deliveries/SLUG --profile PROFILE.json --reproduce --json",
}
SKILLS = {
    "orient": {"docs": ["readme", "about", "repair", "params"], "rules": None},
    "author-building": {"docs": ["g1", "g5"], "rules": ["building", "room"]},
    "decorate-interior": {"docs": ["g2"], "rules": ["material"]},
    "author-furniture-library": {"docs": ["g3"], "rules": ["furniture"]},
    "accept-and-package-delivery": {"docs": ["g4"], "rules": ["package"]},
    "submit-delivery": {"docs": ["sub"], "rules": ["submission"]},
}
PURPOSE = [
    (r"^AGENTS\.md$", "agent entry point: what the set is, where to start, commands", ["entry", "agent"]),
    (r"^llms\.txt$", "index of the set for language-model readers", ["entry", "agent", "index"]),
    (r"^llms-full\.txt$", "all guide content in marked chunks, one file", ["agent", "content"]),
    (r"^README\.md$", "human index of the set and rule levels", ["entry", "human"]),
    (r"^ABOUT\.md$", "what the set is, who it is for, how a consumer adopts it", ["entry", "human"]),
    (r"^(CHANGELOG|VERSIONING|CONTRIBUTING|LICENSE)\.md$", "project policy document", ["policy", "human"]),
    (r"^07-profile-parameters\.md$", "every profile parameter with defaults (generated)", ["profile", "generated"]),
    (r"^profiles/profile\.schema\.json$", "JSON Schema of a consumer profile", ["profile", "schema", "machine"]),
    (r"^profiles/", "consumer profile (parameters and rule levels)", ["profile", "machine"]),
    (r"^REPAIR-LOOP\.md$", "run, read findings, fix, rerun procedure with stop conditions", ["procedure", "agent"]),
    (r"^0[1-5]-.*\.md$", "human guide", ["guide", "human"]),
    (r"^08-submissions-and-ingest\.md$", "how outside deliveries are submitted as pull requests and ingested after a merge", ["guide", "human", "submission"]),
    (r"^06-rules-index\.md$", "all rules in one table (generated)", ["rules", "generated"]),
    (r"^rules\.json$", "machine-readable rule registry (generated)", ["rules", "generated", "machine"]),
    (r"^chunks/index\.json$", "index of the content chunks (generated)", ["index", "generated", "machine"]),
    (r"^chunks/", "guide section chunk of about 1,500 tokens or less (generated)", ["content", "generated", "chunk"]),
    (r"^skills/[^/]+/SKILL\.md$", "skill: when to use, ordered procedure, commands, definition of done", ["skill", "agent"]),
    (r"^skills/[^/]+/references/rules\.md$", "rules for this skill with fix hints (generated)", ["skill", "rules", "generated"]),
    (r"^skills/[^/]+/references/", "guide chunk for this skill, loaded on demand (generated)", ["skill", "reference", "generated"]),
    (r"^skills/[^/]+/scripts/", "wrapper that runs the set's tools", ["skill", "script"]),
    (r"^schemas/", "JSON Schema", ["schema", "machine"]),
    (r"^templates/", "starting file", ["template"]),
    (r"^tools/rules_meta\.json$", "machine fields of the rules (source of truth with the guides)", ["rules", "source"]),
    (r"^tools/.*\.py$", "command-line tool", ["tool", "script"]),
    (r"^tools/", "tool support file", ["tool"]),
    (r"^MANIFEST\.json$", "this file", ["index", "machine"]),
    (r"^\.gitignore$", "version control ignore list", ["config"]),
]


OVERLAY = {}


def read(rel):
    if rel in OVERLAY:
        return OVERLAY[rel]
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def approx_tokens(text):
    return (len(text) + 3) // 4


def slug(text, n=48):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].strip("-") or "section"


# ------------------------------------------------------------------ rules.json
def flat_params():
    out = set()

    def walk(d, pre):
        for k, v in d.items():
            p = pre + k
            out.add(p)
            if isinstance(v, dict) and k not in ("propertyNames", "propertyValues", "ruleLevels"):
                walk(v, p + ".")
    walk(json.loads(read("profiles/default.json")), "")
    return out


def rules_json(rules, order):
    meta = json.loads(read("tools/rules_meta.json"))["rules"]
    problems = [i for i in order if i not in meta] + ["meta has %s" % i for i in meta if i not in rules]
    known = flat_params()
    for i in order:
        if i in meta:
            for p in meta[i].get("parameters", []):
                if p not in known:
                    problems.append("%s names the unknown profile parameter %s" % (i, p))
            if meta[i].get("extension") != rules[i]["extension"]:
                problems.append("%s: extension differs between the guide (%s) and rules_meta.json (%s)" % (i, rules[i]["extension"], meta[i].get("extension")))
    if problems:
        sys.exit("rules_meta.json and the guides disagree: " + ", ".join(problems))
    out = []
    for rid in order:
        r, m = rules[rid], meta[rid]
        tool = m.get("tool")
        if tool:
            how = {"tool": "tools/%s.py" % tool, "command": TOOL_CMD[tool], "method": "automated: the finding carries rule id %s" % rid}
            if m.get("estimate"):
                how["method"] = ("automated estimate: the finding carries rule id %s; the script approximates the rule (%s), so a person "
                                 "confirms it and a consumer should not raise it to required lightly" % (rid, m["estimate"]))
        else:
            how = {"tool": None, "command": None, "method": "review: no script checks this rule; compare the finished work with the statement"}
        fix = m.get("fix_hint") or ""
        if not fix or fix.startswith("Change the work so that it meets the rule statement"):
            fix = "Change the work so that it meets the rule: " + r["statement"]
        out.append({"id": rid, "level": r["level"].lower(), "applies_to": m["applies_to"], "guide": r["guide"],
                    "statement": r["statement"], "rationale": m["rationale"], "how_to_check": how,
                    "automated": bool(tool), "fix_hint": fix, "examples": m["examples"], "related": m["related"],
                    "parameters": m.get("parameters", []), "extension": rules[rid]["extension"]})
    return {"format": "rules/1", "version": VERSION, "count": len(out), "rules": out}


# ------------------------------------------------------------------ profile parameters document
def params_doc():
    schema = json.loads(read("profiles/profile.schema.json"))
    default = json.loads(read("profiles/default.json"))
    strict = json.loads(read("profiles/example-strict.json"))
    robj = OVERLAY.get("__rules__", {})
    used = {}
    for r in robj.get("rules", []):
        for p in r["parameters"]:
            used.setdefault(p, []).append(r["id"])
    rows = []

    def walk(sch, d, s, pre):
        for k, v in sch.get("properties", {}).items():
            p = pre + k
            if k in ("format", "name", "version", "description"):
                continue
            if v.get("type") == "object" and "properties" in v:
                walk(v, d.get(k, {}), s.get(k, {}), p + ".")
            else:
                rows.append((p, v.get("description", ""), d.get(k), s.get(k)))
    walk(schema, default, strict, "")

    def show(x):
        t = json.dumps(x)
        return "`%s`" % (t if len(t) <= 60 else t[:57] + "...")
    out = ["<!-- SPDX-License-Identifier: CC-BY-4.0 -->", "# Profile parameters", "",
           "Every value that depends on a consumer is a parameter of a profile (`profiles/profile.schema.json`). This table is "
           "generated from the schema and the two profiles that come with the set. `default` is `profiles/default.json`; `strict` is the "
           "illustrative consumer profile `profiles/example-strict.json`. A consumer publishes its own profile in the same shape; a "
           "parameter it omits takes the default.", "",
           "| Parameter | Meaning | default | strict | Rules |", "|---|---|---|---|---|"]
    for p, desc, dv, sv in rows:
        out.append("| `%s` | %s | %s | %s | %s |" % (p, desc.replace("|", "/"), show(dv), show(sv), ", ".join(used.get(p, [])) or "-"))
    out += ["", "## Rule levels in a profile", "",
            "`ruleLevels` maps a rule id to `required`, `recommended` or `off`. The strict example makes these rules required: "
            + ", ".join(sorted(k for k, v in strict.get("ruleLevels", {}).items() if v == "required")) + ".", "",
            "## Extensions", "",
            "An extension is an optional group of rules. It applies only when `extensions.<name>.enabled` is true: `walkability` "
            "(for consumers that place people or agents in rooms), `luminaires` (fixtures become lights), `signboards` (signs are "
            "generated from declared boards), `furnitureCollision` (furniture is approximated by a simple collider), `terrain` "
            "(the consumer's terrain source supplies the ground; the file carries a derived, read-only terrain patch). Rules that belong "
            "to an extension carry its name after the level, for example `B-90 REQUIRED luminaires`, and `rules.json` lists it in "
            "`extension`.", ""]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ chunks
def split_doc(text):
    """Pieces of (title, text): by H2, then H3, then paragraph blocks, each at most MAX_CHUNK_CHARS."""
    lines = text.split("\n")
    pieces, cur_title, cur = [], "Introduction", []
    for ln in lines:
        if ln.startswith("## ") and cur:
            pieces.append((cur_title, "\n".join(cur)))
            cur_title, cur = ln[3:].strip(), [ln]
        else:
            if ln.startswith("## "):
                cur_title = ln[3:].strip()
            cur.append(ln)
    pieces.append((cur_title, "\n".join(cur)))
    out = []
    for title, body in pieces:
        if len(body) <= MAX_CHUNK_CHARS:
            out.append((title, body))
            continue
        subs, st, cur = [], title, []
        for ln in body.split("\n"):
            if ln.startswith("### ") and cur:
                subs.append((st, "\n".join(cur)))
                st, cur = "%s: %s" % (title, ln[4:].strip()), [ln]
            else:
                cur.append(ln)
        subs.append((st, "\n".join(cur)))
        for st, sb in subs:
            if len(sb) <= MAX_CHUNK_CHARS:
                out.append((st, sb))
                continue
            block, parts = "", []
            paras = []
            for para in sb.split("\n\n"):
                if len(para) <= MAX_CHUNK_CHARS:
                    paras.append(para)
                    continue
                lines = para.split("\n")          # an over-long table or list: split by lines, repeating a table header
                head = lines[:2] if lines[0].startswith("|") else []
                cur = []
                for ln in lines:
                    if cur and sum(len(x) + 1 for x in cur) + len(ln) > MAX_CHUNK_CHARS:
                        paras.append("\n".join(cur))
                        cur = list(head) + ([ln] if ln not in head else [])
                    else:
                        cur.append(ln)
                paras.append("\n".join(cur))
            for para in paras:
                if block and len(block) + len(para) + 2 > MAX_CHUNK_CHARS:
                    parts.append(block)
                    block = para
                else:
                    block = (block + "\n\n" + para) if block else para
            parts.append(block)
            for k, ptxt in enumerate(parts, 1):
                out.append(("%s (part %d of %d)" % (st, k, len(parts)), ptxt))
    return out


def chunks():
    files, index, seen = {}, [], set()
    for key, fn in DOCS:
        if not os.path.exists(os.path.join(ROOT, fn)):
            continue
        for n, (title, body) in enumerate(split_doc(read(fn)), 1):
            ids = sorted(set(re.findall(r"\*\*([BDFX]-\d+[a-z]?) ·", body)))
            name = "%s--%s.md" % (key, slug(title))
            k = 2
            while name in seen:
                name = "%s--%s-%d.md" % (key, slug(title), k)
                k += 1
            seen.add(name)
            head = "<!-- chunk: %s | source: %s | title: %s | rules: %s -->\n" % (name[:-3], fn, title, ",".join(ids) or "-")
            text = head + body.rstrip("\n") + "\n"
            files["chunks/" + name] = text
            index.append({"id": name[:-3], "file": "chunks/" + name, "source": fn, "title": title,
                          "approx_tokens": approx_tokens(text), "rules": ids})
    files["chunks/index.json"] = json.dumps({"format": "chunk-index/1", "maxChunkChars": MAX_CHUNK_CHARS, "chunks": index}, indent=1) + "\n"
    return files, index


# ------------------------------------------------------------------ llms files
def llms(index, skills_present, count):
    L = ["# Authoring guide set: IFC buildings, materials and furniture", "",
         "> Application-neutral rules, tools and skills for building, decorating, furnishing and packaging IFC deliveries that any "
         "compatible consumer can use. Static files only: read them, run the Python tools, fix, repeat until no REQUIRED finding remains.", "",
         "Version %s. %d rules (see rules.json): REQUIRED rules must pass, RECOMMENDED rules should. Commands are plain "
         "`python3 tools/...` lines; nothing here assumes a particular agent harness." % (VERSION, count), "",
         "## Start here", "",
         "- [AGENTS.md](AGENTS.md): what this set is, commands, working rules",
         "- [skills/orient/SKILL.md](skills/orient/SKILL.md): pick the right skill for the task",
         "- [REPAIR-LOOP.md](REPAIR-LOOP.md): run, read findings, fix, rerun; stop conditions", "",
         "## Skills", ""]
    for s in skills_present:
        L.append("- [skills/%s/SKILL.md](skills/%s/SKILL.md)" % (s, s))
    L += ["", "## Rules and schemas", "",
          "- [rules.json](rules.json): all rules with level, applies_to, how_to_check, fix_hint, examples",
          "- [schemas/rules.schema.json](schemas/rules.schema.json): shape of rules.json",
          "- [schemas/check-report.schema.json](schemas/check-report.schema.json): shape of every checker's --json output",
          "- [schemas/manifest.schema.json](schemas/manifest.schema.json): delivery manifest",
          "- [schemas/material-library.schema.json](schemas/material-library.schema.json): material library",
          "- [schemas/item.schema.json](schemas/item.schema.json): furniture item description",
          "- [schemas/building-metadata.schema.json](schemas/building-metadata.schema.json): building summary",
          "- [schemas/finish-schedule.schema.json](schemas/finish-schedule.schema.json): finish schedule",
          "- [schemas/set.schema.json](schemas/set.schema.json): texture set description",
          "- [schemas/submission.schema.json](schemas/submission.schema.json): the submission block of a submitted delivery",
          "- [schemas/proofs.schema.json](schemas/proofs.schema.json): proofs/manifest.json of a delivery (GLB files, validation report, renders)",
          "- [schemas/placements.schema.json](schemas/placements.schema.json): the placements table written by tools/export_glb.py for a GLB with per-product origins",
          "- [schemas/walk-report.schema.json](schemas/walk-report.schema.json): the report of tools/walkcheck.py",
          "- [schemas/catalogue.schema.json](schemas/catalogue.schema.json): the neutral catalogue written by tools/ingest.py", "",
          "## Tools", "",
          "- [tools/check_all.py](tools/check_all.py): one command, one JSON report, per deliverable type",
          "- [tools/check_submission.py](tools/check_submission.py): form checks of a submitted delivery (X-70 to X-78)",
          "- [tools/build_proofs.py](tools/build_proofs.py): makes a delivery's proofs: GLB files, validation report, standard renders, manifest (X-79 to X-86)",
          "- [tools/check_proofs.py](tools/check_proofs.py): checks the proofs; `--reproduce` rebuilds and compares them",
          "- [tools/export_glb.py](tools/export_glb.py), [tools/validate_glb.py](tools/validate_glb.py), [tools/render.py](tools/render.py): IFC to GLB, GLB validation, headless renders",
          "- [tools/coplanar.py](tools/coplanar.py), [tools/walkcheck.py](tools/walkcheck.py), [tools/check_set.py](tools/check_set.py): coincident faces in a GLB, a 3D walk at a body radius, check of a staged copy of the set",
          "- [tools/ingest.py](tools/ingest.py): turns an accepted (merged) delivery into component assets and a catalogue",
          "- [tools/README.md](tools/README.md): every tool", "",
          "## Guide sections (each file is about 1,500 tokens or less)", ""]
    for c in index:
        if c["source"].startswith(("0", "R")):
            note = c["title"] + ("; rules " + ", ".join(c["rules"][:6]) + (" ..." if len(c["rules"]) > 6 else "") if c["rules"] else "")
            L.append("- [%s](%s): %s" % (c["id"], c["file"], note))
    L += ["", "## Optional", "",
          "- [llms-full.txt](llms-full.txt): every section above in one file, in marked chunks",
          "- [README.md](README.md): index for people",
          "- [06-rules-index.md](06-rules-index.md): the rules as one table",
          "- [MANIFEST.json](MANIFEST.json): every file with purpose, tags and hash", ""]
    return "\n".join(L)


def llms_full(files, index):
    parts = ["# Authoring guide set: full content", "",
             "> Every guide section in one file, in order. Each chunk starts with a comment line `<!-- chunk: id | source | title | rules -->`. "
             "Prefer the single chunk files (chunks/index.json) when you only need one topic.", ""]
    for c in index:
        parts.append(files[c["file"]].rstrip("\n"))
        parts.append("\n---\n")
    return "\n".join(parts) + "\n"


# ------------------------------------------------------------------ skills references
def skill_refs(files, index, rules_obj):
    out = {}
    for name, cfg in SKILLS.items():
        base = "skills/%s/references/" % name
        for c in index:
            if c["id"].split("--")[0] in cfg["docs"]:
                out[base + os.path.basename(c["file"])] = files[c["file"]]
        if cfg["rules"]:
            rows = [r for r in rules_obj["rules"] if set(r["applies_to"]) & set(cfg["rules"])]
            t = ["# Rules for this skill", "", "Generated from rules.json. Level, statement, how to check, fix hint.", "",
                 "| Rule | Level | Statement | Check | Fix hint |", "|---|---|---|---|---|"]
            for r in rows:
                chk = r["how_to_check"]["tool"] or "review"
                t.append("| %s | %s | %s | %s | %s |" % (r["id"], r["level"], r["statement"].replace("|", "/"), chk, r["fix_hint"].replace("|", "/")))
            out[base + "rules.md"] = "\n".join(t) + "\n"
    return out


# ------------------------------------------------------------------ manifest
def sha(b):
    return hashlib.sha256(b).hexdigest()


def manifest(overlay):
    rows = []
    paths = (set(overlay) | set(fileset.set_files(ROOT))) - {"MANIFEST.json"}
    for rel in sorted(paths):
        if rel in overlay:
            b = overlay[rel].encode("utf-8")
        else:
            with open(os.path.join(ROOT, rel), "rb") as fh:
                b = fh.read()
        purpose, tags = "supporting file", []
        for pat, p, t in PURPOSE:
            if re.search(pat, rel):
                purpose, tags = p, t
                break
        rows.append({"path": rel, "purpose": purpose, "tags": tags, "sha256": sha(b), "bytes": len(b)})
    return json.dumps({"format": "set-manifest/1", "version": VERSION,
                       "note": "Every file of the set (the list is tools/fileset.py) except dist/ and MANIFEST.sha256 (see MANIFEST.sha256 and dist/SHA256SUMS.txt).",
                       "files": rows}, indent=1) + "\n"


def generate():
    rules, order = rules_index.collect()
    problems = rules_index.cross_check(rules)
    if problems:
        sys.exit("\n".join(problems))
    out = {"06-rules-index.md": rules_index.render(rules, order)}
    robj = rules_json(rules, order)
    out["rules.json"] = json.dumps(robj, indent=1) + "\n"
    OVERLAY["__rules__"] = robj
    out["07-profile-parameters.md"] = params_doc()
    OVERLAY["07-profile-parameters.md"] = out["07-profile-parameters.md"]
    cf, index = chunks()
    out.update(cf)
    skills_present = [s for s in SKILLS if os.path.exists(os.path.join(ROOT, "skills", s, "SKILL.md"))]
    out["llms.txt"] = llms(index, skills_present, robj["count"])
    out["llms-full.txt"] = llms_full(cf, index)
    out.update(skill_refs(cf, index, robj))
    out["MANIFEST.json"] = manifest(out)
    return out


def existing_generated(out):
    """Generated files on disk that the generator no longer produces (stale)."""
    stale = []
    for sub in ("chunks", "skills"):
        d = os.path.join(ROOT, sub)
        for base, dirs, names in os.walk(d):
            for n in names:
                rel = os.path.relpath(os.path.join(base, n), ROOT).replace(os.sep, "/")
                gen = rel.startswith("chunks/") or "/references/" in rel
                if gen and rel not in out:
                    stale.append(rel)
    return stale


def main():
    if "--check" not in sys.argv and "--write" not in sys.argv:
        print(__doc__)
        sys.exit(2)
    out = generate()
    stale = existing_generated(out)
    if "--check" in sys.argv:
        bad = []
        for rel, text in out.items():
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p) or open(p, encoding="utf-8").read() != text:
                bad.append(rel)
        sums = os.path.join(ROOT, fileset.CHECKSUM_FILE)
        if not os.path.exists(sums) or open(sums, encoding="utf-8").read() != fileset.checksum_text(ROOT):
            bad.append(fileset.CHECKSUM_FILE)
        if bad or stale:
            print("generated files out of date: %s" % ", ".join((bad + ["(stale) " + s for s in stale])[:12]))
            sys.exit(1)
        print("generated files are current (%d files)" % len(out))
        return
    for rel in stale:
        os.remove(os.path.join(ROOT, rel))
    if stale:
        out = generate()       # the manifest must not list files that were just removed
    for rel, text in out.items():
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    with open(os.path.join(ROOT, fileset.CHECKSUM_FILE), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fileset.checksum_text(ROOT))              # last: it hashes everything written above
    print("wrote %d generated files and %s" % (len(out), fileset.CHECKSUM_FILE))


if __name__ == "__main__":
    main()
