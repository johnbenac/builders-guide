---
name: author-building
description: Author an IFC4 building (levels, rooms, walls, doors, windows, floors, roofs, stairs, and optionally lights and signs) that many different consumers can open, identify rooms in and use. Use when creating or fixing a building model, writing room ids and occupants, placing doors and openings, declaring luminaires or signboards for a consumer that supports them, or when a check reports a B-rule finding.
license: CC-BY-4.0
metadata:
  version: "2.2.0"
  rules: "B-01 to B-144"
---

# Author a building

## Inputs

* The consumer's profile (default `profiles/default.json`): limits, frame and level offset, identifier rules, allowed occupants,
  geometry values, build volume, keep-outs, floors the consumer supplies, extensions. See `references/g1--2-what-the-profile-gives-you.md`.
  Ask the consumer for what is missing.
* The programme: rooms, their use, sizes, levels.
* Python with `ifcopenshell` (see `tools/requirements.txt`).

## Procedure

1. **Start from the fixture.** Run `python3 tools/make_sample.py work/` and read `tools/make_sample.py`: it writes a complete valid
   room (level, walls, openings, door, window, slabs, room with properties, table, covering, luminaire) with `ifcopenshell`. For anything
   larger use the authoring kit `tools/ifc_author.py` (levels, slabs, walls with openings, stairs with wells sized for head-room, gable
   roofs, battered walls, internal and open-air rooms) and copy the nearest of the three buildings in `tools/make_fixtures.py`: a
   cantilevered tray house, a rotated hillside block on a slope with two ground-contact levels, a courtyard with battered walls. Sizes,
   ids and colours change; the structure and relations do not.
2. **Frame.** An IFC edition the profile accepts, metres, Z up, the profile's horizontal axes; author in the placement the profile expects
   (B-01, B-02, B-10, B-11). Keep `GlobalId` values stable (B-70); number entities from the profile's start when it assigns one (B-71).
   Write the frame note (B-12).
3. **Levels.** One `IfcBuildingStorey` per level with `Name` and `Elevation`; contain or aggregate every element (B-13).
4. **Rooms.** One `IfcSpace` per room: extruded floor outline, flat floor; properties `RoomId` (unique, within the profile's length and
   pattern), `Occupant` (from the profile's list when it has one), `Function` (B-20 to B-26). Streets and paths are rooms too (B-29).
5. **Fabric.** Walls as `IfcWall`; every door and window fills an `IfcOpeningElement` that voids its wall (B-41, B-44); keep doorways
   clear (B-42); floors as `IfcSlab` unless the consumer supplies the floor (B-50, B-51); stairs as `IfcStairFlight` in any building
   with more than one level (B-60, B-62).
6. **Reservations.** Volumes that must stay clear: `IfcSpatialZone` plus a proxy with `PredefinedType` `PROVISIONFORSPACE` (B-80, B-81).
7. **Extensions, only if the profile enables them.** Luminaires: an assembly of a housing and an emissive part with all the
   profile's properties, positions in the consumer's global frame (B-90 to B-93). Signboards: B-100 to B-102. Walkability: free
   standing points (B-33). Terrain context: see step 7a. Open-air rooms (terraces, courtyards, decks): `EXTERNAL` and `Enclosed` false
   (B-143). Pitched roofs and leaning walls: B-144. Nothing but slabs, footings, piles, walls, stairs and ramps below the lowest floor (B-142).
7a. **Terrain context, only if the profile enables `extensions.terrain`.** Terrain belongs to the profile's terrain source, not to
   you: never author it, cut a pad into it or model water (B-115, B-130, B-139). Run `tools/site_request.py` (ask for the finished
   floor elevation above sea level and the building origin in the site frame; do not guess them) and send the request to the source;
   it returns a GeoTIFF height patch and a sidecar after grading the pad. Run `tools/terrain_import.py` with both and the request. For
   tests only, `tools/make_sample_terrain.py` writes a plane or slope. Declare every level that touches the ground with `GroundContact`
   true in `Pset_Declaration_Level` (`b.level(..., ground_contact=True)` in the kit; B-141) and pass the building's azimuth to
   `site_request.py` when the file's +X axis is not east. Keep `frame.levelOffsetMetres` at 0 (B-133). The importer
   refuses a patch whose hash differs from its sidecar and a request made for another version of the master file.
8. **Colours.** Distinct finish, distinct colour per class (D-01); opacity below 1 only for glass (D-04).
9. **Check and repair.** Run the command below; follow `REPAIR-LOOP.md`. To see what you built, run
   `python3 tools/preview.py work/ifc/MASTER.ifc work/preview` (one plan per level, one isometric view) and look at it; the checker
   estimates room overlap (B-30), reachability (B-47), a roof or slab over every room (B-54) and stair head-room (B-61), but you decide
   whether the plan is what you meant.
10. **Summaries.** Write `tables/rooms.csv` (`templates/rooms.template.csv`) and `tables/building.json`
    (`schemas/building-metadata.schema.json`).

## Commands

```
python3 tools/check_all.py work/ifc/MASTER.ifc --profile PROFILE.json --json --out report.json
python3 tools/check_ifc.py work/ifc/MASTER.ifc --profile PROFILE.json --finish-schedule finishes/finish-schedule.json --json
python3 scripts/run_tool.py check_all work/ifc/MASTER.ifc --json
python3 tools/site_request.py work/ifc/MASTER.ifc --floor-elevation H --origin E N [--azimuth DEG] --out site-request.json    # terrain extension
python3 tools/terrain_import.py patch.tif patch.json work/ifc/MASTER.ifc --request site-request.json --out work/ifc/MASTER-terrain.ifc
```

If the consumer's profile renames declaration properties, write the neutral names and run
`python3 tools/map_properties.py in.ifc out.ifc --mapping PROFILE.json` before checking with that profile.

## Reading the report

`result` is `pass`/`fail`/`error`; `profile` names the profile used. For each finding with `status` `fail`: `rule`, `message`,
`location.element` (the `GlobalId` of the product), `fix_hint`. `finishKeys` in the IFC sub-report lists every (class, colour, opacity)
that needs a finish entry (D-03). `info` findings tell you which extensions the profile left off, so their rules were not checked.

## Stop conditions

* A profile value is missing (level offset, identifier rules, occupants): ask the consumer.
* Same finding after three runs: report it.
* File over the profile's limits (B-05): simplify before anything else.

## Definition of done

`check_all.py` exits 0 on the master file with the profile; rooms table and building summary written; `finishKeys` handed to the
decorating step.

## References (load on demand)

| Topic | File |
|---|---|
| all rules of this skill with fix hints | `references/rules.md` |
| file, units, frame, levels | `references/g1--3-file-and-schema.md`, `references/g1--4-units-axes-origin-and-levels.md` |
| rooms and ids | `references/g1--5-rooms-and-zones.md` |
| walls, doors, windows | `references/g1--6-walls-doors-windows-and-openings.md` |
| floors, roofs, ceilings | `references/g1--7-floors-roofs-ceilings-and-slab-openings.md` |
| stairs, ramps, lifts, rails | `references/g1--8-circulation-stairs-ramps-lifts-rails.md` |
| ids and property sets | `references/g1--9-names-identifiers-property-sets-and-classifica.md` |
| reservations | `references/g1--10-zones-and-reserved-volumes.md` |
| lights (extension) | `references/g1--11-optional-extension-lighting-fixtures.md` |
| signs (extension) | `references/g1--12-optional-extension-signboards.md` |
| terrain context (extension): flow and frames, rules | `references/g1--16-optional-extension-terrain-context.md`, `references/g1--17-terrain-context-the-rules.md` |
| hygiene and budgets | `references/g1--13-geometry-hygiene.md`, `references/g1--14-level-of-detail-and-budgets.md` |
| a complete small example | `references/g5--2-what-is-modelled.md` |
| larger examples (stairs, several levels, slopes, courtyards) | `references/g5--6-larger-examples.md` |
