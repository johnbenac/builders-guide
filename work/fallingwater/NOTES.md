# Cantilevered house over a stream: build notes

Built with `skills/author-building` and the default profile (`profiles/default.json`), since no consumer profile was given.

```
python3 work/fallingwater/build_fallingwater.py work/fallingwater/out
python3 tools/check_all.py work/fallingwater/out/ifc/fallingwater-master.ifc --json --out work/fallingwater/out/report.json
```

Result: 0 required failures, 0 warnings. 3 levels (0, 3, 6 m), 10 rooms (7 enclosed, 3 open-air terraces),
12 doors, 19 windows, 3 stair flights, stone core and chimney, cantilevered trays with parapets, hearth boulder.
`out/preview.png` is a quick render made with matplotlib (not part of the guide set).

## What this model is not

The plan, sizes and room layout are my approximation from memory of the house. The repo has no way to take drawings or a survey,
and I had none. Read it as a massing study with the right ideas (stacked trays, cantilevers, stone core, stream-side hatch stair),
not as a measured reproduction.

## What the repo lacks for a faithful recreation

1. **Source data and a way to bring it in.** No plans, sections, elevations or dimension tables, and no guidance on turning them into
   an IFC (scale, tracing, tolerances). Fidelity cannot be checked: `check_ifc.py` tests rules, not likeness.
2. **Site, terrain and water.** Now covered by the terrain extension (guide 1, sections 16 and 17): the terrain source owns the ground and
   the water; the file carries a derived, read-only terrain patch plus water metadata. `add_terrain.sh` runs the whole chain on this house
   with synthetic sloped ground standing in for the source's patch (`out/ifc/fallingwater-terrain.ifc`, checked against
   `profile-terrain.json`). The real rock ledge, stream and waterfall would come from the source; the house is not graded to them here.
3. **Below the lowest level.** Partly open: the georeference now carries the floor height above sea level (`OrthogonalHeight`), but there is
   still no rule for stairs or landings below level 0, such as the hatch stair that ends in the air at the stream.
4. **Open-air rooms.** B-29 wants terraces declared as rooms, but B-20 makes a room an extrusion to a ceiling. I gave terraces a nominal
   2.65 m height. There is no property or class for "unroofed", so `enclosed: no` lives only in `rooms.csv`.
5. **Structure and glazing systems.** Only `IfcSlab`/`IfcWall` are covered. Nothing on beams, posts, reinforced trays or cantilever
   structure, nor on corner windows and steel mullions (the red frames), which need two openings meeting at a corner with no pier.
   Windows here are single flat panes in a wall opening.
6. **Irregular and curved forms, and masonry surfaces.** The boulder is a low-poly extruded polygon. There is no guidance for natural
   stone, rubble coursing or roughness. `decorate-interior` covers texture sets, but the repo ships no stone or concrete images.
7. **Built-ins.** The skill for furniture is an item library; built-in desks, benches, shelves and the kitchen have no home.
8. **Preview.** No viewer or renderer in `tools/`. `ifcopenshell` and `matplotlib` had to be installed to see the result
   (`matplotlib` is not in `tools/requirements.txt`).
9. **Packaging inputs.** I did not write finishes, a finish schedule or a delivery package, so D-03 (finish coverage) is unchecked.
   That is work left undone, not a repo limit.

## Terrain test run

```
work/fallingwater/add_terrain.sh
```

Floor at 412.0 m above sea level, building origin at the site centre, ground rising 0.1 m per metre to the north. The synthetic patch
reduces to 2 triangles; the checker's terrain rules B-130 to B-140 pass. `out/preview-terrain.png` is the render.

## Left out by me (scope, not a repo limit)

The entry bridge and carport, the guest house with its covered walk, the stair from the master terrace down to the living terrace,
luminaires (the default profile has the extension off) and furniture.

## Changed outside `work/`

`tools/gen_all.py` now skips `work/` when building the manifest (this was done before the terrain work). `AGENTS.md` tells agents to write output to `work/`, and any file
there made `test_sync.py` fail. `MANIFEST.json` was regenerated to match.
