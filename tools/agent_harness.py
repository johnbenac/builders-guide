#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Simulates a fresh agent that has only this set, under two profiles.

    python3 tools/agent_harness.py [WORK_DIR] [--json]

For each of profiles/default.json and profiles/example-strict.json the harness
  A. follows the documented path (AGENTS.md, orient skill, building / decorate / furniture / package skills): builds a minimal
     building, one material library and one furniture item, repairs the first failing check by reading the findings, packages
     everything and requires `check_all.py` to exit 0 with zero REQUIRED findings on every deliverable;
  B. breaks the work in every rule category and requires the JSON findings to carry the right rule id, a severity and a fix hint
     (rules whose extension the profile leaves off, or whose level the profile lowers, are expected to behave accordingly).
Every report is validated against schemas/check-report.schema.json and must name the profile it used. Exit status 0 only if
everything held.

Requires: pip install -r tools/requirements.txt
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import ifcopenshell

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
args = [a for a in sys.argv[1:] if not a.startswith("--")]
work_root = os.path.abspath(args[0]) if args else tempfile.mkdtemp(prefix="agent-harness-")
os.makedirs(work_root, exist_ok=True)
log, problems = [], []

try:
    import jsonschema
    CHECK_SCHEMA = json.load(open(os.path.join(ROOT, "schemas", "check-report.schema.json")))
except ImportError:
    jsonschema, CHECK_SCHEMA = None, None
RULES = {r["id"]: r for r in json.load(open(os.path.join(ROOT, "rules.json")))["rules"]}
PROFILES = [("default", os.path.join(ROOT, "profiles", "default.json")),
            ("example-strict", os.path.join(ROOT, "profiles", "example-strict.json"))]


def note(msg):
    log.append(msg)
    if "--json" not in sys.argv:
        print(msg)


def expect(cond, msg):
    if not cond:
        problems.append(msg)
        note("  PROBLEM: " + msg)
    return cond


def tool(script, *a):
    return subprocess.run([sys.executable, os.path.join(HERE, script), *a], capture_output=True, text=True)


def run_profile(label, profile_path):
    prof = json.load(open(profile_path))
    names = prof.get("propertyNames", {})
    work = os.path.join(work_root, label)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    note("== profile %s ==" % label)

    def level_of(rule):
        return (prof.get("ruleLevels", {}).get(rule) or RULES[rule]["level"]).upper()

    def ext_on(rule):
        e = RULES[rule]["extension"]
        return e is None or prof["extensions"][e]["enabled"]

    def to_consumer(path):
        """Rename the neutral declaration properties to the consumer's names (the intake step), when the profile has any."""
        if not names:
            return path
        out = os.path.join(work, "mapped-" + os.path.basename(path))
        p = tool("map_properties.py", path, out, "--mapping", profile_path)
        expect(p.returncode == 0, "map_properties failed: " + p.stderr[-200:])
        return out

    def check_all(path, *extra):
        p = tool("check_all.py", path, "--json", "--profile", profile_path, *extra)
        rep = json.loads(p.stdout)
        if jsonschema:
            try:
                jsonschema.validate(rep, CHECK_SCHEMA)
                for sub in rep.get("reports", []):
                    jsonschema.validate(sub, CHECK_SCHEMA)
            except jsonschema.ValidationError as exc:
                expect(False, "a report does not match check-report.schema.json: %s" % exc.message[:120])
        expect(rep["profile"]["name"] == prof["name"], "the report names profile %s, not %s" % (rep["profile"]["name"], prof["name"]))
        expect(p.returncode == rep["exitCode"], "exit status %d differs from the report's exitCode %d" % (p.returncode, rep["exitCode"]))
        return rep

    def fails(rep):
        return [f for f in rep["findings"] if f["status"] == "fail"]

    # ---------------------------------------------------------------- A1 building
    note("A1 building (start from the fixture, adapt it)")
    src = open(os.path.join(HERE, "make_sample.py"), encoding="utf-8").read()
    src = (src.replace("EX-001", "AG-101").replace("Example Occupant", "Agent Occupant").replace("Example work room", "Agent work room")
           .replace("W, D, T, H = 5.2, 4.2, 0.2, 3.0", "W, D, T, H = 6.2, 4.6, 0.2, 3.0").replace("UL-EX-01", "UL-AG-01")
           .replace("B-EXAMPLE", "B-AGENT").replace("example-room-master.ifc", "agent-master.ifc")
           .replace("tbl_origin = (2.6, 2.1)", "tbl_origin = (3.1, 2.3)"))
    build_py = os.path.join(work, "agent_build.py")
    open(build_py, "w", encoding="utf-8").write(src)
    pkg = os.path.join(work, "agent-building-1.0.0")
    os.makedirs(pkg)
    p = subprocess.run([sys.executable, build_py, pkg], capture_output=True, text=True)
    expect(p.returncode == 0, "the adapted fixture did not run: " + p.stderr[-200:])
    master = os.path.join(pkg, "ifc", "agent-master.ifc")
    sched_path = os.path.join(pkg, "finishes", "finish-schedule.json")
    os.makedirs(os.path.dirname(sched_path), exist_ok=True)
    json.dump({"format": "finish-schedule/1", "delivery": "agent-building-1.0.0", "version": "1.0.0", "materials": [], "floors": [
        {"id": "floor-default", "where": {"occupant": "*"}, "finish": {"set": "plaster_example"}}], "libraries": []}, open(sched_path, "w"))
    cm = to_consumer(master)
    rep = check_all(cm, "--finish-schedule", sched_path)
    d03 = [f for f in fails(rep) if f["rule"] == "D-03"]
    expect(rep["exitCode"] == 1 and d03 and d03[0]["fix_hint"], "repair loop: expected a D-03 failure with a fix hint on the empty schedule")
    note("  run 1: %d REQUIRED failure(s): %s" % (rep["summary"]["requiredFailures"], sorted({f["rule"] for f in fails(rep)})))
    keys = [r for r in rep["reports"] if r["tool"] == "check_ifc.py"][0]["finishKeys"]
    mats = []
    for k in keys:
        faces = ({"top": {"set": "plaster_example"}, "side": {"set": "plaster_example"}, "bottom": {"set": "plaster_example"}}
                 if k["class"] == "IfcSlab" else {"all": {"set": "plaster_example", "tint": "ifc", "tintStrength": 0.6}})
        m = {"key": {"class": k["class"], "colour": k["colour"], "opacity": k["opacity"]}, "role": k["class"] + " finish", "usedBy": "agent room"}
        if k["opacity"] < 0.99:
            m["glass"] = {"fresnelAlpha": 0.5}
        elif k["colour"] == "#fff0cf":
            m.update(keep=True, reason="emissive part")
        else:
            m["faces"] = faces
        mats.append(m)
    sched = json.load(open(sched_path))
    sched["materials"] = mats
    sched["libraries"] = [{"name": "plaster_example", "version": "1.0.0"}]
    json.dump(sched, open(sched_path, "w"), indent=1)
    rep = check_all(cm, "--finish-schedule", sched_path)
    expect(rep["exitCode"] == 0 and rep["summary"]["requiredFailures"] == 0, "building still fails after the repair: %s" % [(f["rule"], f["message"]) for f in fails(rep)][:3])
    note("  run 2: exit %d, %d REQUIRED failure(s)" % (rep["exitCode"], rep["summary"]["requiredFailures"]))
    ifc_report = [r for r in rep["reports"] if r["tool"] == "check_ifc.py"][0]
    os.makedirs(os.path.join(pkg, "reports"), exist_ok=True)
    # the delivered master stays neutral; the report in the package is for it, so rerun on the neutral file under this profile's numbers
    p = tool("check_ifc.py", master, "--profile", profile_path, "--finish-schedule", sched_path, "--report", os.path.join(pkg, "reports", "check_ifc.json"))
    if names:        # a neutral file under a renaming profile lacks the consumer's names: record the report of the consumer-named copy
        shutil.copy(cm, os.path.join(work, "consumer-copy.ifc"))
        rep2 = json.loads(tool("check_ifc.py", cm, "--profile", profile_path, "--finish-schedule", sched_path, "--json").stdout)
        rep2["target"]["path"] = os.path.basename(master)
        rep2["file"] = os.path.basename(master)
        rep2["sha256"] = rep2["target"]["sha256"] = ifc_sha = __import__("hashlib").sha256(open(master, "rb").read()).hexdigest()
        json.dump(rep2, open(os.path.join(pkg, "reports", "check_ifc.json"), "w"), indent=1)
        ifc_report = rep2

    # ---------------------------------------------------------------- A2 material library
    note("A2 material library")
    subprocess.run([sys.executable, os.path.join(HERE, "make_sample_texture_set.py"), pkg], check=True, capture_output=True)
    json.dump({"format": "material-library/1", "name": "agent-finishes", "version": "1.0.0",
               "sets": [{"name": "plaster_example", "version": "1.0.0", "path": "textures/plaster_example"}], "schedule": "finish-schedule.json"},
              open(os.path.join(pkg, "finishes", "library.json"), "w"), indent=1)
    open(os.path.join(pkg, "finishes", "SOURCES.csv"), "w").write(
        "asset,type,source,licence,notes\nfinishes/textures/plaster_example,texture set,procedural: tools/make_sample_texture_set.py seed 7,free to reuse (example),\n")
    rep = check_all(os.path.join(pkg, "finishes"))
    expect(rep["exitCode"] == 0, "material library fails: %s" % [f["message"] for f in fails(rep)][:3])
    note("  material: exit %d, %d check(s)" % (rep["exitCode"], len(rep["reports"])))

    # ---------------------------------------------------------------- A3 furniture
    note("A3 furniture item")
    subprocess.run([sys.executable, os.path.join(HERE, "make_sample_item.py"), pkg], check=True, capture_output=True)
    rep = check_all(os.path.join(pkg, "items"))
    expect(rep["exitCode"] == 0, "furniture fails: %s" % [f["message"] for f in fails(rep)][:3])
    note("  furniture: exit %d" % rep["exitCode"])

    # ---------------------------------------------------------------- A4 package
    note("A4 package")
    os.makedirs(os.path.join(pkg, "tables"), exist_ok=True)
    if not os.path.exists(os.path.join(pkg, "tables", "rooms.csv")):
        open(os.path.join(pkg, "tables", "rooms.csv"), "w").write("roomId,name\nAG-101,Agent work room\n")
    json.dump({"format": "building-metadata/1", "building": {"id": "B-AGENT", "name": "Agent building"},
               "frame": {"units": "metres", "axes": "+X forward, +Y left, +Z up", "levelOffsetMetres": prof["frame"]["levelOffsetMetres"]},
               "ifc": {"path": "ifc/agent-master.ifc", "schema": "IFC4"},
               "levels": [{"name": "Example building - ground / +0 m", "elevationMetres": 0.0, "rooms": 1}], "occupants": ["Agent Occupant"],
               "roomIdPrefix": "AG"}, open(os.path.join(pkg, "tables", "building.json"), "w"), indent=1)
    os.makedirs(os.path.join(pkg, "notes"), exist_ok=True)
    open(os.path.join(pkg, "notes", "changes.md"), "w").write("# Changes\n\n## 1.0.0\n\nFirst delivery.\n")
    meta = {"delivery": {"id": "agent-building", "title": "Agent harness building", "version": "1.0.0", "created": "2026-10-22T00:00:00Z",
                         "supersedes": None, "kind": ["building", "materials", "furniture"]},
            "author": {"organisation": "Harness", "role": "test", "contact": "none"}, "profile": {"name": prof["name"], "version": prof["version"]},
            "frame": {"units": "metres", "axes": "+X forward, +Y left, +Z up", "levelOffsetMetres": prof["frame"]["levelOffsetMetres"],
                      "localZero": "finished floor of the lowest level"},
            "ifc": {"schema": "IFC4"}, "counts": ifc_report["counts"],
            "provenance": [{"asset": "ifc/agent-master.ifc", "type": "ifc-model", "source": "original", "author": "Harness", "licence": "free to reuse"},
                           {"asset": "finishes/textures/plaster_example", "type": "texture-set", "source": "procedural", "author": "Harness", "licence": "free to reuse"},
                           {"asset": "items/table.work.1600", "type": "item", "source": "original", "author": "Harness", "licence": "free to reuse"}],
            "licence": {"statement": "Free to reuse (test)."},
            "checks": {"tool": "check_ifc.py", "toolVersion": "2.3.0", "report": "reports/check_ifc.json", "result": "pass"}}
    meta_path = os.path.join(work, "package-meta.json")
    json.dump(meta, open(meta_path, "w"))
    p = tool("build_package.py", "init", pkg, meta_path)
    expect(p.returncode == 0, "build_package init failed: " + p.stderr[-200:])
    # the package check of the master needs the consumer's names; verify the package parts that do not read the model, plus the manifest
    rep = json.loads(tool("build_package.py", "verify", pkg, "--profile", profile_path, "--json").stdout)
    expect(rep["exitCode"] == 0, "package verify fails: %s" % [(f["rule"], f["message"]) for f in rep["findings"] if f["status"] == "fail"][:3])
    if not names:
        rep = check_all(pkg)
        expect(rep["exitCode"] == 0 and rep["summary"]["requiredFailures"] == 0, "package fails: %s" % [(f["rule"], f["message"]) for f in fails(rep)][:3])
        note("  package: exit %d, %d REQUIRED failure(s), %d RECOMMENDED warning(s), %d check(s)" % (
            rep["exitCode"], rep["summary"]["requiredFailures"], rep["summary"]["recommendedWarnings"], len(rep["reports"])))
    else:
        note("  package: manifest verified (the master is checked in its consumer-named copy above)")

    # ---------------------------------------------------------------- B deliberate faults
    note("B deliberate faults: the right rule id, a severity and a fix hint (levels follow the profile)")

    def verdict(name, rule, rep):
        if not ext_on(rule):
            note("  %-22s %-5s skipped: extension %s is off in this profile" % (name, rule, RULES[rule]["extension"]))
            return
        lvl = level_of(rule)
        hit = [f for f in rep["findings"] if f["rule"] == rule and f["status"] in ("fail", "warn")]
        ok = bool(hit) and bool(hit[0].get("fix_hint")) and hit[0]["id"].startswith(rule + "@")
        if ok:
            ok = hit[0]["status"] == ("fail" if lvl == "REQUIRED" else "warn") and hit[0]["level"] == lvl
        if ok and lvl == "REQUIRED":
            ok = rep["exitCode"] == 1
        expect(ok, "%s: expected %s as %s with a fix hint under %s" % (name, rule, lvl, label))
        note("  %-22s %-5s %-11s %s" % (name, rule, lvl, "ok" if ok else "MISSING"))

    def prop(m, name):
        return [p for p in m.by_type("IfcPropertySingleValue") if p.Name == name][0]

    def ifc_fault(name, rule, fn):
        m = ifcopenshell.open(master)
        fn(m)
        out = os.path.join(work, "broken-%s.ifc" % name)
        m.write(out)
        verdict(name, rule, check_all(to_consumer(out), "--finish-schedule", sched_path))

    def f_long(m): prop(m, "RoomId").NominalValue = m.create_entity("IfcText", wrappedValue="A" * 70)
    def f_noid(m): prop(m, "RoomId").Name = "RoomRef"
    def f_noocc(m): prop(m, "Occupant").Name = "Org"
    def f_fill(m): m.remove([r for r in m.by_type("IfcRelFillsElement") if r.RelatedBuildingElement.is_a("IfcDoor")][0])
    def f_block(m): m.by_type("IfcFurnishingElement")[0].ObjectPlacement.RelativePlacement.Location.Coordinates = (1.4, 0.3, 0.0)
    def f_floor(m): [m.remove(s) for s in m.by_type("IfcSlab") if s.PredefinedType == "FLOOR"]
    def f_lens(m): [setattr(e, "Name", e.Name[:-5] + " glow") for e in m.by_type("IfcLightFixture") if e.Name.endswith(" lens")]
    def f_pos(m): prop(m, "LightPosition").NominalValue = m.create_entity("IfcText", wrappedValue="3.1,2.3,30")
    def f_miss(m): prop(m, "LightRangeM").Name = "Range"
    def f_guid(m):
        w = m.by_type("IfcWall")
        w[1].GlobalId = w[0].GlobalId

    def f_level(m):
        for rel in m.by_type("IfcRelContainedInSpatialStructure"):
            rel.RelatedElements = [x for x in rel.RelatedElements if not x.is_a("IfcCovering")]

    ifc_fault("room-id-too-long", "B-23", f_long)
    ifc_fault("room-id-missing", "B-26", f_noid)
    ifc_fault("occupant-missing", "B-24", f_noocc)
    ifc_fault("door-no-opening", "B-41", f_fill)
    ifc_fault("door-blocked", "B-42", f_block)
    ifc_fault("no-floor-slab", "B-50", f_floor)
    ifc_fault("lens-name", "B-90", f_lens)
    ifc_fault("light-position", "B-92", f_pos)
    ifc_fault("light-property", "B-91", f_miss)
    ifc_fault("duplicate-guid", "B-70", f_guid)
    ifc_fault("element-no-level", "B-13", f_level)

    bad_sched = os.path.join(work, "bad-schedule.json")
    s2 = json.load(open(sched_path))
    s2["materials"] = s2["materials"][1:]
    json.dump(s2, open(bad_sched, "w"))
    verdict("schedule-missing-key", "D-03", check_all(cm, "--finish-schedule", bad_sched))

    tex = os.path.join(pkg, "finishes", "textures", "plaster_example")
    tmp = os.path.join(work, "tex-broken")
    shutil.copytree(tex, tmp)
    os.remove(os.path.join(tmp, "orm.png"))
    verdict("texture-map-missing", "D-40", json.loads(tool("check_texture_set.py", tmp, "--profile", profile_path, "--json").stdout))
    shutil.copy(os.path.join(tex, "orm.png"), tmp)
    m = json.load(open(os.path.join(tmp, "set.json")))
    m["tileMetres"] = 0
    json.dump(m, open(os.path.join(tmp, "set.json"), "w"))
    verdict("texture-tile-size", "D-43", json.loads(tool("check_texture_set.py", tmp, "--profile", profile_path, "--json").stdout))

    item = os.path.join(pkg, "items", "table.work.1600")
    tmpi = os.path.join(work, "items-broken", "table.work.1600")
    shutil.copytree(item, tmpi)
    d = json.load(open(os.path.join(tmpi, "table.work.1600.item.json")))
    d["class"] = "IfcBuildingElementProxy"
    d["dimensions"]["x"] = 2.5
    json.dump(d, open(os.path.join(tmpi, "table.work.1600.item.json"), "w"))
    rep = json.loads(tool("check_item.py", tmpi, "--profile", profile_path, "--json").stdout)
    verdict("item-class", "F-01", rep)
    verdict("item-dimensions", "F-22", rep)

    def pkg_fault(name, rule, fn):
        p2 = os.path.join(work, "pkg-" + name)
        shutil.copytree(pkg, p2)
        fn(p2)
        verdict(name, rule, json.loads(tool("build_package.py", "verify", p2, "--profile", profile_path, "--json").stdout))

    def p_tamper(p2): open(os.path.join(p2, "notes", "changes.md"), "a").write("x\n")
    def p_extra(p2): open(os.path.join(p2, "notes", "extra.txt"), "w").write("x\n")

    def p_lic(p2):
        mp = os.path.join(p2, "manifest.json")
        mm = json.load(open(mp))
        mm["licence"]["statement"] = ""
        json.dump(mm, open(mp, "w"))

    def p_prov(p2):
        mp = os.path.join(p2, "manifest.json")
        mm = json.load(open(mp))
        mm["provenance"] = mm["provenance"][1:]
        json.dump(mm, open(mp, "w"))

    def p_master2(p2):
        shutil.copy(os.path.join(p2, "ifc", "agent-master.ifc"), os.path.join(p2, "ifc", "second.ifc"))
        tool("build_package.py", "init", p2, meta_path)

    pkg_fault("package-hash", "X-11", p_tamper)
    pkg_fault("package-unlisted", "X-12", p_extra)
    pkg_fault("package-licence", "X-21", p_lic)
    pkg_fault("package-provenance", "X-20", p_prov)
    pkg_fault("package-two-masters", "X-13", p_master2)
    p = tool("check_all.py", os.path.join(work, "does-not-exist.ifc"), "--json")
    expect(p.returncode == 3 and json.loads(p.stdout)["result"] == "error", "a missing input must give exit code 3")
    note("  %-22s %-5s %s" % ("missing-input", "exit3", "ok" if p.returncode == 3 else "MISSING"))


for label, path in PROFILES:
    run_profile(label, path)

summary = {"result": "fail" if problems else "pass", "problems": problems, "workDir": work_root, "profiles": [l for l, _ in PROFILES]}
if "--json" in sys.argv:
    print(json.dumps(summary, indent=1))
else:
    print("agent_harness: %s (%d problem(s))" % (summary["result"].upper(), len(problems)))
sys.exit(1 if problems else 0)
