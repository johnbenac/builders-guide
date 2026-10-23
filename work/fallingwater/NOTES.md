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
2. **Site, terrain and water.** B-115 says not to model terrain or relief unless the profile says how, and no profile does. The rock
   ledge, the stream and the waterfall, which the house exists for, cannot be expressed. `baseSurfaces` in the profile schema looks like
   the hook, but nothing says how a consumer-supplied ground or water surface is described or how a building sits on it.
3. **Below the lowest level.** B-11/B-12 define local z = 0 as the finished floor of the lowest level. The hatch stair drops 2.6 m below
   it and ends in the air at the stream. No rule covers elements below level 0, open-air stairs, or landings at a natural surface.
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

## Left out by me (scope, not a repo limit)

The entry bridge and carport, the guest house with its covered walk, the stair from the master terrace down to the living terrace,
luminaires (the default profile has the extension off) and furniture.

## Changed outside `work/`

`tools/gen_all.py` now skips `work/` when building the manifest. `AGENTS.md` tells agents to write output to `work/`, and any file
there made `test_sync.py` fail. `MANIFEST.json` was regenerated to match.
