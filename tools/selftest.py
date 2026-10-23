#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Self-test of the checker: build the worked example, check that it passes, then break it in ten ways and check
that the checker names the right rule each time.

    python3 selftest.py [WORK_DIR]

Requires: pip install -r tools/requirements-terrain.txt (and requirements-preview.txt for the preview check)
"""
import json
import os
import subprocess
import sys
import tempfile

import ifcopenshell

HERE = os.path.dirname(os.path.abspath(__file__))
work = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="selftest-")
os.makedirs(work, exist_ok=True)

subprocess.run([sys.executable, os.path.join(HERE, "make_sample.py"), work], check=True, stdout=subprocess.DEVNULL)
base = os.path.join(work, "ifc", "example-room-master.ifc")


PROFILE = os.path.join(work, "selftest-profile.json")
with open(PROFILE, "w") as fh:        # the default profile with a level offset and the extensions the faults need
    json.dump({"format": "profile/1", "name": "selftest", "version": "1.0.0", "frame": {"levelOffsetMetres": 12.0},
               "identifiers": {"entityNumberStart": 700001, "roomIdMaxLength": 7},
               "ruleLevels": {"B-24": "required", "B-26": "required", "B-50": "required"},
               "extensions": {"walkability": {"enabled": True}, "luminaires": {"enabled": True}}}, fh)


def run(path, *extra):
    rep = path + ".report.json"
    p = subprocess.run([sys.executable, os.path.join(HERE, "check_ifc.py"), path, "--profile", PROFILE,
                        "--report", rep, *extra], capture_output=True, text=True)
    with open(rep) as fh:
        return p.returncode, json.load(fh)


rc, rep = run(base)
assert rc == 0 and rep["result"] == "pass", "the worked example must pass: %s" % rep["findings"]
print("worked example: PASS (%s)" % ", ".join("%s %s" % (v, k) for k, v in rep["counts"].items()))


def mutate(name, rule, fn):
    m = ifcopenshell.open(base)
    fn(m)
    out = os.path.join(work, "broken-%s.ifc" % name)
    m.write(out)
    rc, rep = run(out)
    hit = [f for f in rep["findings"] if f["rule"] == rule and f["status"] in ("fail", "warn")]
    ok = bool(hit) and (rc == 1 or hit[0]["level"] == "RECOMMENDED")
    print("%-22s expects %-5s -> %s" % (name, rule, "caught" if ok else "NOT CAUGHT"))
    if not ok:
        print(json.dumps(rep["findings"], indent=1))
        sys.exit(1)


def prop_of(m, cls, name):
    for p in m.by_type("IfcPropertySingleValue"):
        if p.Name == name:
            return p
    raise KeyError(name)


def long_id(m):
    prop_of(m, "IfcSpace", "RoomId").NominalValue = m.create_entity("IfcText", wrappedValue="TOOLONGID")


def drop_fill(m):
    for rel in m.by_type("IfcRelFillsElement"):
        if rel.RelatedBuildingElement.is_a("IfcDoor"):
            m.remove(rel)
            break


def move_light(m):
    prop_of(m, "", "LightPosition").NominalValue = m.create_entity("IfcText", wrappedValue="2.6,2.1,20")


def rename_lens(m):
    for e in m.by_type("IfcLightFixture"):
        if e.Name.endswith(" lens"):
            e.Name = e.Name[:-5] + " glow"


def block_door(m):
    t = m.by_type("IfcFurnishingElement")[0]
    t.ObjectPlacement.RelativePlacement.Location.Coordinates = (1.4, 0.3, 0.0)


def drop_floor(m):
    for s in m.by_type("IfcSlab"):
        if s.PredefinedType == "FLOOR":
            m.remove(s)


def dup_guid(m):
    ws = m.by_type("IfcWall")
    ws[1].GlobalId = ws[0].GlobalId


def enum_roomid(m):
    p = prop_of(m, "IfcSpace", "RoomId")
    p.NominalValue = None
    p.Name = "RoomId"
    e = m.create_entity("IfcPropertyEnumeratedValue", Name="RoomId", EnumerationValues=[m.create_entity("IfcLabel", wrappedValue="EX-001")])
    for ps in m.by_type("IfcPropertySet"):
        if p in (ps.HasProperties or ()):
            ps.HasProperties = [e if x == p else x for x in ps.HasProperties]
    m.remove(p)


def no_level(m):
    for rel in m.by_type("IfcRelContainedInSpatialStructure"):
        rel.RelatedElements = [x for x in rel.RelatedElements if not x.is_a("IfcCovering")]


def glass_wall(m):
    for st in m.by_type("IfcSurfaceStyleRendering"):
        if abs(st.SurfaceColour.Red - 0x8c / 255.0) < 1e-3:       # the covering colour
            st.Transparency = 0.5


mutate("long-roomid", "B-23", long_id)
mutate("door-no-opening", "B-41", drop_fill)
mutate("light-position", "B-92", move_light)
mutate("lens-name", "B-90", rename_lens)
mutate("door-blocked", "B-42", block_door)
mutate("no-floor-slab", "B-50", drop_floor)
mutate("duplicate-guid", "B-70", dup_guid)
mutate("enumerated-roomid", "B-72", enum_roomid)
mutate("element-no-level", "B-13", no_level)
mutate("opaque-as-glass", "D-04", glass_wall)

# non-ASCII byte in a text value
with open(base, "rb") as fh:
    raw = fh.read().replace(b"Example Occupant", b"Example Occupant \xb7")
bad = os.path.join(work, "broken-nonascii.ifc")
with open(bad, "wb") as fh:
    fh.write(raw)
rc, rep = run(bad)
assert any(f["rule"] == "B-04" and f["status"] == "fail" for f in rep["findings"]), "non-ASCII not caught"
print("%-22s expects %-5s -> caught" % ("non-ascii", "B-04"))

# the templates and the sample files match their schemas
try:
    import jsonschema
    root = os.path.join(HERE, "..")
    pairs = [("schemas/finish-schedule.schema.json", "templates/finish-schedule.template.json"),
             ("schemas/item.schema.json", "templates/item.template.json")]
    for sch, doc in pairs:
        with open(os.path.join(root, sch)) as fh:
            schema = json.load(fh)
        with open(os.path.join(root, doc)) as fh:
            jsonschema.validate(json.load(fh), schema)
        print("%-40s matches %s" % (doc, sch))
except ImportError:
    print("jsonschema not installed: template checks skipped")
subprocess.run([sys.executable, os.path.join(HERE, "test_map_properties.py"), os.path.join(work, "map")], check=True)
subprocess.run([sys.executable, os.path.join(HERE, "test_terrain.py"), os.path.join(work, "terrain")], check=True)
subprocess.run([sys.executable, os.path.join(HERE, "test_fixtures.py"), os.path.join(work, "fixtures")], check=True)
subprocess.run([sys.executable, os.path.join(HERE, "test_hardening.py"), os.path.join(work, "hardening")], check=True)
subprocess.run([sys.executable, os.path.join(HERE, "test_sync.py")], check=True)
subprocess.run([sys.executable, os.path.join(HERE, "agent_harness.py"), os.path.join(work, "harness")], check=True, stdout=subprocess.DEVNULL)
print("agent_harness: passed")
print("selftest: all checks behaved as expected")
