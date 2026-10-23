<!-- chunk: g4--5-acceptance-checks | source: 04-delivery-and-acceptance-guide.md | title: 5. Acceptance checks | rules: X-40 -->
## 5. Acceptance checks

Acceptance is a list of checks. The first group is what you run yourself with the scripts; the second is what a receiving party typically checks, so you know what will be looked at.

### 5.1 Checks you run before sending

One command runs everything that applies to a deliverable and prints one JSON report (`schemas/check-report.schema.json`):
`python3 tools/check_all.py PATH --json --profile PROFILE.json`, where PATH is a master file, a `finishes/` folder, an `items/` folder or a package folder. Without `--profile` the default profile is used, and the report says which profile it checked against. Every tool below also takes `--json` and `--profile`. Exit codes: 0 no REQUIRED failure, 1 at least one, 2 wrong command line, 3 unreadable input. The loop for fixing findings is in `REPAIR-LOOP.md`.

```
python3 tools/check_all.py ifc/MASTER.ifc --profile PROFILE.json --json --out reports/check_all.json
python3 tools/check_ifc.py ifc/MASTER.ifc --profile PROFILE.json --finish-schedule finishes/finish-schedule.json --report reports/check_ifc.json
python3 tools/check_texture_set.py finishes/textures/SETNAME --preview wrap.png --report reports/check_texture_set.json
python3 tools/check_item.py items/ITEMID --report reports/check_item-ITEMID.json
python3 tools/build_package.py verify PACKAGE_FOLDER
```

| Script | What it checks | Rules |
|---|---|---|
| `check_all.py` | runs everything below that applies to the path | all |
| `check_ifc.py` | schema, units, text form, size and triangle limits, levels and containment, rooms (floor, identifiers, occupants, function), doorways, windows, floor slabs, stairs and risers, reservation volumes, zones, optional luminaire and signboard declarations, build volume, finish colours, identifiers | B-01 to B-120, D-03 to D-05 |
| `check_texture_set.py` | maps present, 8-bit RGB PNG, same square size, tangent-basis normal, packed occlusion-roughness-metalness, tile size, texel density, luminance, wrap seam, `set.json` fields | D-40 to D-49 |
| `check_item.py` | one item at the origin, class, declared dimensions against geometry, pivot, collision box, triangle budget, item id | F-01 to F-51 |
| `build_package.py verify` | manifest against the schema, every hash and size, no unlisted files, one master, package size, provenance and licence, the check report belongs to the master and passed | X-10 to X-40 |

**X-40 · REQUIRED** - Run `check_ifc.py` on the exact master file you are sending, with the profile, and include its JSON report in the package. The report records the SHA-256 of the master file it checked and the profile it used; a report for a different file is not accepted. A delivery with any REQUIRED failure in the report is not sent.

Findings have a fixed shape, which a receiving party also uses when it sends work back (section 7):

```json
{ "id": "B-41@1a2b3c4d", "rule": "B-41", "level": "REQUIRED", "status": "fail", "severity": "error",
  "location": { "file": "master.ifc", "element": "3Z2k6lcTnJFPCzw1CFlWEi" },
  "message": "IfcDoor Entrance door is not linked to an opening in a wall",
  "fix_hint": "Add an IfcOpeningElement in the wall with IfcRelVoidsElement ... and IfcRelFillsElement ..." }
```

`status` is `pass`, `info`, `warn` (a RECOMMENDED rule not met) or `fail` (a REQUIRED rule not met). `element` is the `GlobalId` of the product concerned.

Rules the script can only estimate say "estimate" in their message: the standing-point check (B-33), the sign text fit and legibility (B-101, B-102) and the riser check (B-61). A person confirms those.

### 5.2 Checks a receiving party typically makes

| # | Check | What it looks at | Rule |
|---|---|---|---|
| 1 | package intake | every hash and size, the layout, the manifest | X-10 to X-14 |
| 2 | reading | the master opens in an accepted schema edition with a metre length unit and within the limits | B-01, B-02, B-05 |
| 3 | identity | `GlobalId` values and entity numbers are unique across everything held; room and zone identifiers are unique | B-22, B-70, B-71, B-81 |
| 4 | rooms | each room has geometry and a floor; rooms can be classified | B-20 to B-26 |
| 5 | doorways | each door's opening is found, the rooms either side are listed, the opening is clear | B-41, B-42 |
| 6 | windows | window openings cut their walls | B-44 |
| 7 | standing points | (walkability extension) every room has a free standing point | B-33, B-50 |
| 8 | stairs and ramps | stairs connect levels; risers and slopes within the profile | B-60 to B-65 |
| 9 | reservation volumes | provisions are marked, not solid | B-80 |
| 10 | light fixtures | (luminaires extension) required properties, positions match | B-90 to B-93 |
| 11 | signs | (signboards extension) boards fit their text and are legible | B-100 to B-102 |
| 12 | materials | every colour has a finish; every named texture set exists with matching hashes | D-03, D-40 |
| 13 | build volume | no vertex outside the volume or inside a keep-out | B-110 |
| 14 | repeatability | the same input gives the same result; unchanged identifiers stay | B-07, B-75 |
