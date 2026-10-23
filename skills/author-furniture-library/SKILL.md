---
name: author-furniture-library
description: Create a library of reusable furniture, fixtures and accent items as IFC4 files with item description files (pivot, dimensions, collision box, clearances, anchors, placement rules, variants) that can be placed in any compatible consumer. Use when modelling a table, chair, bed, shelf, lamp or equipment item, writing an item description, instancing items into a building, or when a check reports an F-rule finding.
license: CC-BY-4.0
metadata:
  version: "2.2.0"
  rules: "F-01 to F-72"
---

# Author a furniture library

Many consumers approximate furniture with one axis-aligned box per element (the profile's `extensions.furnitureCollision`) and keep
start points clear of it. Most have no sit points or moving parts. Item data beyond the model is for placement tools; write it anyway.

## Inputs

* The list of items wanted, with real sizes.
* The profile (`budgets.maxItemTriangles`, `limits.*`, extensions) and any finishes the consumer already has.
* Python with `ifcopenshell` and `numpy`.

## Procedure

1. **Fixture.** `python3 tools/make_sample_item.py work/` writes one valid item and its description. Copy the pattern.
2. **Class.** `IfcFurnishingElement` for movable furniture; `IfcBuildingElementProxy` only when exact collision shape matters (F-01).
   `ObjectType` from the category list (F-02).
3. **Model.** One element at the origin, no rotation, no scale; lowest point at z = 0; pivot at the footprint centre for floor items;
   +X is the front (F-10, F-20, F-21). Keep it cheap: within `budgets.maxItemTriangles` (F-51).
4. **Collision.** If a single box fits badly (L-shaped sofa), deliver several box-like elements (F-40, when the extension is on). Rotate
   placements in 90 degree steps (F-41). Never rely on walking under or through an item (F-43).
5. **Properties.** `Pset_Declaration_Item` with `ItemId`, `ItemVersion`, `Role` (F-03).
6. **Description.** `<itemId>.item.json` from `templates/item.template.json`: pivot, front, dimensions, footprint, collision,
   clearances, anchors, placement rules, variants (F-12, F-30 to F-32, F-60). Validate against `schemas/item.schema.json`.
7. **Colours.** Items take their look from the building's finish schedule: one or two colours per ordinary item, no textures (F-52, F-53).
8. **Instances in a building.** Each instance has its own `GlobalId`, a level, and a mapped item sharing geometry (F-61, F-62).
9. **Fixtures.** Light fixtures and signs follow the building skill when the profile enables those extensions (F-70).
10. **Check.** `python3 tools/check_all.py items/ --profile PROFILE.json --json`; repair per `REPAIR-LOOP.md`.

## Commands

```
python3 tools/check_all.py items/ --profile PROFILE.json --json --out report.json
python3 tools/check_item.py items/table.work.1600 --profile PROFILE.json --json
```

## Reading the report

F-01 `fail` (REQUIRED): the IFC class differs from the description. `warn` findings (RECOMMENDED) with fix hints cover the item file
layout (F-10), pivot (F-21), dimensions (F-22), collision box (F-42), triangles (F-51), ids (F-03, F-11) and the description (F-12).

## Stop conditions

* A real size is unknown: ask; do not guess dimensions.
* Same finding after three runs: report it.

## Definition of done

`check_all.py` exits 0 on `items/`; every item has a description that matches its model; provenance and licence recorded for the
package step.

## References (load on demand)

| Topic | File |
|---|---|
| all rules of this skill with fix hints | `references/rules.md` |
| what consumers do with an item | `references/g3--1-what-consumers-do-with-an-item.md` |
| classes and categories | `references/g3--2-classes-and-categories.md` |
| library format and description file | `references/g3--3-item-library-format.md` |
| pivot and dimensions | `references/g3--4-dimensions-origin-and-pivot.md` |
| anchors, placement, clearances | `references/g3--5-placement-points-anchors-and-where-an-item-may.md` |
| collision and budgets | `references/g3--6-collision-and-footprint.md`, `references/g3--7-polygon-and-texture-budgets.md` |
| variants and instancing | `references/g3--8-variants-and-instancing.md` |
| fixtures | `references/g3--9-fixtures.md` |
