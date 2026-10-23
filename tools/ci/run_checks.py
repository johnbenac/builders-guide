#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check submitted deliveries the way the pull-request workflow does. Called by run_checks.sh.

    python3 tools/ci/run_checks.py [--base REF] [--out DIR] [SLUG ...]

For each delivery (deliveries/<slug>/): check_submission.py and check_all.py under profiles/default.json, and under profiles/<name>.json
when delivery.json names a profile that exists there. Every JSON report is written to DIR (default ci-reports) with summary.md. The
delivery is only read: nothing in it is run. Exit 0 when no REQUIRED rule failed, 1 otherwise.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOOLS = os.path.join(ROOT, "tools")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PROFILE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def run(args, timeout=600):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=ROOT)


def changed(base):
    p = run(["git", "diff", "--name-only", "%s...HEAD" % base])
    if p.returncode:
        p = run(["git", "diff", "--name-only", base, "HEAD"])
    if p.returncode:
        sys.exit("cannot compare with %s: %s" % (base, p.stderr.strip()[:200]))
    files = [x for x in p.stdout.split("\n") if x]
    slugs = sorted({f.split("/")[1] for f in files if f.startswith("deliveries/") and f.count("/") >= 2})
    others = [f for f in files if not f.startswith("deliveries/")]
    return slugs, others


def main():
    args, base, out, slugs = sys.argv[1:], None, "ci-reports", []
    while args:
        a = args.pop(0)
        if a == "--base":
            base = args.pop(0)
        elif a == "--out":
            out = args.pop(0)
        elif a in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            slugs.append(a)
    out = os.path.abspath(out)
    others = []
    if base:
        found, others = changed(base)
        slugs = slugs or found
    elif not slugs:
        d = os.path.join(ROOT, "deliveries")
        slugs = sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))) if os.path.isdir(d) else []
    os.makedirs(out, exist_ok=True)
    lines = ["## Delivery checks", ""]
    bad = 0
    if others:
        shown = ", ".join("`%s`" % o for o in others[:6]) + (" and %d more" % (len(others) - 6) if len(others) > 6 else "")
        lines += ["Notice: this change also touches files outside `deliveries/` (%s). A delivery pull request should change only its own " % shown +
                  "folder; reviewers should read any change to tools, profiles or schemas first.", ""]
    if not slugs:
        lines.append("No delivery folder was changed; nothing to check.")
    for slug in slugs:
        d = os.path.join(ROOT, "deliveries", slug)
        if not SLUG.match(slug) or not os.path.isdir(d):
            if SLUG.match(slug) and not os.path.exists(d):
                lines.append("* `%s`: removed in this change; nothing to check." % slug)
                continue
            lines.append("* `%s`: **not a valid delivery folder name** (lower-case letters, digits and single hyphens)" % slug[:60].replace("`", ""))
            bad += 1
            continue
        profiles = [("default", None)]
        try:
            with open(os.path.join(d, "delivery.json"), encoding="utf-8") as fh:
                name = (((json.load(fh).get("submission") or {}).get("profile") or {}).get("name"))
        except (OSError, ValueError, AttributeError):
            name = None
        if isinstance(name, str) and name != "default" and PROFILE.match(name) and os.path.isfile(os.path.join(ROOT, "profiles", name + ".json")):
            profiles.append((name, os.path.join("profiles", name + ".json")))
        lines += ["### `%s`" % slug, "", "| Check | Profile | Result | REQUIRED failures | RECOMMENDED warnings |", "|---|---|---|---|---|"]
        shown = []
        for pname, ppath in profiles:
            for tool, tag in (("check_submission.py", "submission"), ("check_all.py", "all")):
                rep_path = os.path.join(out, "%s.%s.%s.json" % (slug, pname, tag))
                cmd = [sys.executable, os.path.join(TOOLS, tool), os.path.join("deliveries", slug), "--json", "--out", rep_path] + (["--profile", ppath] if ppath else [])
                try:
                    p = run(cmd)
                    with open(rep_path, encoding="utf-8") as fh:
                        rep = json.load(fh)
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    lines.append("| %s | %s | error | - | - |" % (tool, pname))
                    shown.append("%s: could not run (%s)" % (tool, str(exc)[:100]))
                    bad += 1
                    continue
                s = rep["summary"]
                if rep["result"] != "pass" or p.returncode:
                    bad += 1
                lines.append("| %s | %s | %s | %d | %d |" % (tool, pname, rep["result"], s["requiredFailures"], s["recommendedWarnings"]))
                for f in rep["findings"]:
                    if f["status"] == "fail" and len(shown) < 8:
                        shown.append("`%s` %s%s" % (f["rule"], f["message"][:160].replace("`", "'"), (" (fix: %s)" % f["fix_hint"][:140].replace("`", "'")) if f.get("fix_hint") else ""))
                if rep.get("error"):
                    shown.append("%s: %s" % (tool, str(rep["error"])[:160]))
        if shown:
            lines += ["", "First REQUIRED findings:", ""] + ["* " + x for x in shown]
        lines.append("")
    lines += ["", "The full JSON reports are in the `delivery-check-reports` artifact of this run." if os.environ.get("GITHUB_ACTIONS") else
              "The full JSON reports are in `%s`." % out]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
