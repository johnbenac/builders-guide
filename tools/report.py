# SPDX-License-Identifier: Apache-2.0
"""Shared report format of every checker (schema `check-report/1`, see schemas/check-report.schema.json).

Exit codes of every checker:
    0  no REQUIRED rule failed
    1  at least one REQUIRED rule failed (the report lists which)
    2  the command line was wrong
    3  an input could not be read at all (the report, if written, has result "error")
"""
import hashlib
import json
import os

SCHEMA = "check-report/1"
EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_INPUT = 0, 1, 2, 3
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_RULES = None
_PROFILE = None
_PROFILE_INFO = None
DEFAULT_PROFILE = os.path.join(ROOT, "profiles", "default.json")


def _merge(base, over):
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ("propertyNames", "propertyValues", "ruleLevels") else v
    return out


def load_profile(path=None):
    """Load a consumer profile (profiles/profile.schema.json) on top of the default values. Returns the merged dict."""
    global _PROFILE, _PROFILE_INFO
    with open(DEFAULT_PROFILE, encoding="utf-8") as fh:
        base = json.load(fh)
    p = base
    info = {"name": base["name"], "version": base["version"], "sha256": sha256_file(DEFAULT_PROFILE)}
    if path and os.path.abspath(path) != os.path.abspath(DEFAULT_PROFILE):
        with open(path, encoding="utf-8") as fh:
            over = json.load(fh)
        p = _merge(base, over)
        info = {"name": over.get("name", os.path.basename(path)), "version": over.get("version", "?"), "sha256": sha256_file(path)}
    _PROFILE, _PROFILE_INFO = p, info
    return p


def profile():
    return _PROFILE if _PROFILE is not None else load_profile()


def profile_info():
    profile()
    return _PROFILE_INFO


def param(dotted, default=None):
    cur = profile()
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def extension_enabled(name):
    return bool(param("extensions.%s.enabled" % name, False))


def level_of(rule):
    """REQUIRED, RECOMMENDED or OFF: the profile's override, else the level in rules.json."""
    o = profile().get("ruleLevels", {}).get(rule)
    if o:
        return o.upper()
    return rules().get(rule, {}).get("level", "recommended").upper()


def rules():
    """The rule registry (rules.json), or an empty dict when it is not present."""
    global _RULES
    if _RULES is None:
        try:
            with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as fh:
                _RULES = {r["id"]: r for r in json.load(fh)["rules"]}
        except (OSError, ValueError, KeyError):
            _RULES = {}
    return _RULES


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def finding(rule, status, message, element=None, file=None, level=None, **extra):
    """One finding. status: pass, info, warn (RECOMMENDED not met) or fail (REQUIRED not met)."""
    r = rules().get(rule, {})
    lvl = level or level_of(rule)
    if lvl == "OFF":
        return None
    severity = {"fail": "error", "warn": "warning", "info": "info", "pass": "pass"}[status]
    loc = {}
    if file:
        loc["file"] = file
    if element:
        loc["element"] = element
    key = "%s|%s|%s|%s" % (rule, loc.get("file", ""), loc.get("element", ""), message)
    f = {"id": "%s@%s" % (rule, hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]), "rule": rule, "level": lvl,
         "status": status, "severity": severity, "location": loc, "message": message}
    if status in ("fail", "warn"):
        f["fix_hint"] = r.get("fix_hint", "See the rule text in rules.json and the guide section named there.")
    f.update(extra)
    return f


def make_report(tool, version, target, findings, counts=None, extra=None, error=None):
    n_fail = sum(1 for f in findings if f["status"] == "fail")
    n_warn = sum(1 for f in findings if f["status"] == "warn")
    findings = [f for f in findings if f]
    rep = {"schema": SCHEMA, "tool": tool, "toolVersion": version, "target": target,
           "result": "error" if error else ("fail" if n_fail else "pass"),
           "exitCode": EXIT_INPUT if error else (EXIT_FAIL if n_fail else EXIT_PASS),
           "summary": {"requiredFailures": n_fail, "recommendedWarnings": n_warn,
                       "passes": sum(1 for f in findings if f["status"] == "pass"),
                       "info": sum(1 for f in findings if f["status"] == "info")},
           "profile": profile_info(), "counts": counts or {}, "findings": findings}
    if error:
        rep["error"] = error
    if extra:
        rep.update(extra)
    return rep


def target_of(path):
    t = {"path": os.path.basename(path)}
    if os.path.isfile(path):
        t["sha256"] = sha256_file(path)
    return t


def write(rep, path):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rep, fh, indent=1)
        fh.write("\n")


def text_lines(rep):
    for f in rep["findings"]:
        if f["status"] in ("fail", "warn"):
            yield "%-5s %-6s %-11s %s" % (f["status"].upper(), f["rule"], f["level"], f["message"])


def from_rows(rows, file=None):
    """Turn the simple rows of the small checkers into findings."""
    return [f for f in (finding(r["rule"], r["status"], r["message"], file=file, level=r["level"]) for r in rows) if f]
