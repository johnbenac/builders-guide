#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Checks for one library item (guide 3, sections 3 and 4).

    python3 check_item.py ITEM_DIR [--report report.json]

ITEM_DIR holds <itemId>.ifc and <itemId>.item.json (the folder name is the item id). Exits 1 when a REQUIRED rule fails.

Requires: pip install ifcopenshell numpy   (and jsonschema, optional, for the description check)
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.unit

import report as rpt

rows = []


def add(rule, level, ok, msg):
    lvl = rpt.level_of(rule)          # the profile may change a rule's level
    if lvl == "OFF":
        return
    rows.append({"rule": rule, "level": lvl, "status": "pass" if ok else ("fail" if lvl == "REQUIRED" else "warn"), "message": msg})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("item_dir")
    ap.add_argument("--profile", default=None, help="consumer profile; default profiles/default.json")
    ap.add_argument("--report", default=None, help="also write the JSON report to this file")
    ap.add_argument("--json", action="store_true", help="print the JSON report (schema check-report/1) instead of text")
    a = ap.parse_args()
    prof = rpt.load_profile(a.profile)
    if not os.path.isdir(a.item_dir):
        rep = rpt.make_report("check_item.py", "2.3.0", {"path": a.item_dir}, [], error="input not found: %s" % a.item_dir)
        print(json.dumps(rep, indent=1) if a.json else "ERROR input not found: %s" % a.item_dir)
        sys.exit(rep["exitCode"])
    item_id = os.path.basename(os.path.abspath(a.item_dir))
    ifc_path = os.path.join(a.item_dir, item_id + ".ifc")
    desc_path = os.path.join(a.item_dir, item_id + ".item.json")
    if not os.path.exists(ifc_path):
        add("F-10", "RECOMMENDED", False, "missing %s.ifc" % item_id)
        return end(a)
    m = ifcopenshell.open(ifc_path)
    add("B-01", "REQUIRED", m.schema == "IFC4", "schema %s" % m.schema)
    scale = ifcopenshell.util.unit.calculate_unit_scale(m)
    add("B-02", "REQUIRED", abs(scale - 1.0) < 1e-9, "length unit resolves to %g metres" % scale)
    items = [e for e in m.by_type("IfcElement") if e.is_a("IfcFurnishingElement") or e.is_a("IfcBuildingElementProxy")]
    add("F-10", "RECOMMENDED", len(items) == 1, "exactly one furniture or equipment element" if len(items) == 1 else "%d items found; one is expected" % len(items))
    if len(items) != 1:
        return end(a)
    e = items[0]
    # identity placement
    pl = e.ObjectPlacement
    loc = np.array(pl.RelativePlacement.Location.Coordinates, dtype=float) if pl and pl.PlacementRelTo is None else None
    ident = loc is not None and np.allclose(loc, 0.0) and (pl.RelativePlacement.RefDirection is None or list(pl.RelativePlacement.RefDirection.DirectionRatios)[:2] == [1.0, 0.0])
    add("F-10", "RECOMMENDED", bool(ident), "placed at the origin without rotation" if ident else "the item is not placed at the origin without rotation")
    s = ifcopenshell.geom.settings()
    sh = ifcopenshell.geom.create_shape(s, e)
    v = np.array(sh.geometry.verts).reshape(-1, 3)
    mat = ifcopenshell.util.placement.get_local_placement(e.ObjectPlacement)
    v = v @ mat[:3, :3].T + mat[:3, 3]
    tris = len(sh.geometry.faces) // 3
    lo, hi = v.min(0), v.max(0)
    ext = hi - lo
    if not os.path.exists(desc_path):
        add("F-12", "RECOMMENDED", False, "missing %s.item.json" % item_id)
        return end(a)
    with open(desc_path, encoding="utf-8") as fh:
        d = json.load(fh)
    try:
        import jsonschema
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schemas", "item.schema.json")) as fh:
            sch = json.load(fh)
        errs = list(jsonschema.Draft7Validator(sch).iter_errors(d))
        add("F-12", "RECOMMENDED", not errs, "description matches the schema" if not errs else "description: %s" % errs[0].message[:120])
    except ImportError:
        pass
    add("F-11", "RECOMMENDED", d.get("itemId") == item_id, "itemId equals the folder name" if d.get("itemId") == item_id else "itemId %r differs from the folder name" % d.get("itemId"))
    dim = d.get("dimensions", {})
    ok = all(abs(ext[i] - dim.get(k, -9)) <= 0.01 for i, k in enumerate("xyz"))
    add("F-22", "RECOMMENDED", ok, "declared dimensions match the geometry (%.2f x %.2f x %.2f m)" % tuple(ext) if ok else
        "declared dimensions %s differ from the geometry %.3f x %.3f x %.3f m" % (dim, *ext))
    if d.get("pivot", {}).get("kind") == "floor":
        centre = (lo + hi) / 2
        ok = abs(lo[2]) < 1e-3 and abs(centre[0]) < 0.01 and abs(centre[1]) < 0.01
        add("F-21", "RECOMMENDED", ok, "pivot is the footprint centre on the floor" if ok else
            "pivot kind floor needs the footprint centre at x = y = 0 and the lowest point at z = 0 (lowest %.3f, centre %.3f, %.3f)" % (lo[2], centre[0], centre[1]))
    col = d.get("collision", {})
    if col.get("kind") == "box":
        ok = np.allclose(col["min"], lo, atol=0.01) and np.allclose(col["max"], hi, atol=0.01)
        add("F-42", "RECOMMENDED", ok, "declared collision box matches the geometry" if ok else "declared collision box differs from the geometry")
    budget = prof["budgets"]["maxItemTriangles"]
    add("F-51", "RECOMMENDED", tris <= budget, "%d triangles" % tris if tris <= budget else "%d triangles; the profile recommends at most %d for an item" % (tris, budget))
    dt = d.get("budget", {}).get("triangles")
    if dt is not None:
        add("F-51", "RECOMMENDED", dt == tris, "declared triangle budget equals the model" if dt == tris else "declared %d triangles, model has %d" % (dt, tris))
    props = {}
    for rel in e.IsDefinedBy or []:
        if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.is_a("IfcPropertySet"):
            for p in rel.RelatingPropertyDefinition.HasProperties:
                if p.is_a("IfcPropertySingleValue"):
                    props.setdefault(p.Name, p.NominalValue.wrappedValue)
    add("F-03", "RECOMMENDED", props.get("ItemId") == item_id, "ItemId property equals the item id" if props.get("ItemId") == item_id else "ItemId property %r does not equal %r" % (props.get("ItemId"), item_id))
    add("F-01", "REQUIRED", e.is_a() == d.get("class"), "class %s" % e.is_a() if e.is_a() == d.get("class") else "IFC class %s differs from the description %s" % (e.is_a(), d.get("class")))
    end(a)


def end(a):
    name = os.path.basename(os.path.abspath(a.item_dir))
    rep = rpt.make_report("check_item.py", "2.3.0", {"path": name}, rpt.from_rows(rows, name), extra={"item": name})
    if a.report:
        rpt.write(rep, a.report)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        for line in rpt.text_lines(rep):
            print(line)
        print("%s: %s (%d REQUIRED failure(s), %d warning(s))" % (name, rep["result"].upper(), rep["summary"]["requiredFailures"],
              rep["summary"]["recommendedWarnings"]))
    sys.exit(rep["exitCode"])


if __name__ == "__main__":
    main()
