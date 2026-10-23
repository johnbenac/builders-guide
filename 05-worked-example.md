<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Guide 5: Worked example

A complete, minimal delivery: one room with one door, one window, one table, one wall covering and one ceiling light, on one
level, with a finish schedule, a texture set, a library item and a package. It is small enough to read in full, and it passes
every check in guide 4 under both profiles that come with the set: `profiles/default.json` and `profiles/example-strict.json`.

The IFC file is produced by a script, not stored in this set, so that it always matches the script and the version of the IFC
library you have installed, and so that every number below can be reproduced. To build and check everything in one go:

```
pip install -r tools/requirements.txt
python3 tools/run_example.py example-out
```

This writes `example-out/example-room-1.0.0/` (the package), runs every checker on it with the default profile, builds the
manifest and ends with `build_package.py verify`. Run `python3 tools/selftest.py` to see the checker catch deliberate faults in
the same file, and `python3 tools/agent_harness.py` to see a fresh agent build and pass a delivery from the set alone.

## 1. The profiles

| Item | `default.json` | `example-strict.json` |
|---|---|---|
| frame offset | 0 | 12.0 m (declared positions add it) |
| room identifier | up to 64 characters | at most 7 characters, required |
| entity numbers | any | from `#700001` |
| declaration property names | as in the guides | prefixed `Ex_` (the file is renamed by `tools/map_properties.py`) |
| extensions | all off | walkability, luminaires, signboards, furniture collision on |
| limits | 250 MB, 5,000,000 triangles | 100 MB, 3,000,000 triangles |

To check the example against the strict profile, rename the properties and check with it:

```
python3 tools/map_properties.py master.ifc master-strict.ifc --mapping profiles/example-strict.json
python3 tools/check_ifc.py master-strict.ifc --profile profiles/example-strict.json
```

## 2. What is modelled

```
  y
  4.2 +--------------[ window 1.5 x 1.2, sill 0.9 ]----------+
      |                                                       |
      |  covering          (table 1.6 x 0.8,                  |
      |  3.0 x 2.4          light above it)                   |
      |                                                       |
  0.0 +---[ door 1.2 x 2.3 ]----------------------------------+
      0.0                                                    5.2  x
```

| Element | Class | Size and position (file-local metres) |
|---|---|---|
| floor slab | `IfcSlab` `FLOOR` | 5.2 by 4.2 by 0.3, top face at z = 0 |
| roof slab | `IfcSlab` `ROOF` | 5.2 by 4.2 by 0.3, underside at z = 3.0 (the ceiling) |
| south, north, west, east walls | `IfcWall` | 0.2 thick, 3.0 high |
| door opening and door | `IfcOpeningElement`, `IfcDoor` | south wall, x from 0.8 to 2.0, 2.3 high |
| window opening and window | `IfcOpeningElement`, `IfcWindow` | north wall, x from 2.0 to 3.5, from 0.9 to 2.1 high, opacity 0.45 |
| room | `IfcSpace` | inside faces: 4.8 by 3.8 by 3.0, floor at z = 0 |
| table | `IfcFurnishingElement`, mapped item | 1.6 by 0.8 by 0.74, pivot at the footprint centre, placed at (2.6, 2.1, 0) |
| wall covering | `IfcCovering` `CLADDING` | on the west wall's inside face: 10 mm thick, 3.0 m wide, from 0.1 to 2.5 high |
| luminaire | `IfcElementAssembly` with two `IfcLightFixture` parts | centred over the table, emissive part centre at (2.6, 2.1, 2.89) |

## 3. Step by step

### 3.1 Frame, level and identity (B-10 to B-14, B-70, B-71)

The file is IFC4 in metres. The project carries a property set with `FrameNote` and `LevelOffsetMetres = 12.0`. One building and
one level named `Example building - ground / +0 m` with elevation 0. Entity numbers start at `#700001` (the strict profile's range);
every `GlobalId` is derived from a stable key, so the file is identical on every run.

### 3.2 Walls, openings, door and window (B-40 to B-44)

Each wall is an extruded rectangle. The door and the window each have an `IfcOpeningElement` that voids a wall
(`IfcRelVoidsElement`) and is filled by the door or window (`IfcRelFillsElement`). The doorway is 2.3 m high and nothing crosses it.
In the file:

```
#700198=IFCRELVOIDSELEMENT('1C_9SKyzTHcQf6qIs0XZ4T',$,$,$,#700125,#700197);
#700216=IFCDOOR('3Z2k6lcTnJFPCzw1CFlWEi',$,'Entrance door',$,$,#700213,#700215,$,2.3,1.2,.DOOR.,.SINGLE_SWING_LEFT.,$);
#700217=IFCRELFILLSELEMENT('29lMJRl7DVmRJwjxlT70xI',$,$,$,#700197,#700216);
```

### 3.3 Floor, roof and ceiling (B-50, B-53, B-54)

The floor is a slab whose top is the finished floor at z = 0, and the roof slab's underside is the ceiling. Many consumers draw no
ceiling mesh, so that underside is what a person looks up at; guide 2 says how to give it a finish through the slab's `bottom` slot.

### 3.4 The room (B-20 to B-27)

```
#700273=IFCSPACE('1C1BaaS91KOgLuDEt1VXqX',$,'Example work room',$,$,#700270,#700272,'Example work room',.ELEMENT.,.INTERNAL.,0.);
#700274=IFCRELAGGREGATES('3jyuNv4XzQSRLalH7sDq_3',$,$,$,#700034,(#700273));
#700275=IFCPROPERTYSINGLEVALUE('RoomId',$,IFCTEXT('EX-001'),$);
#700276=IFCPROPERTYSINGLEVALUE('Occupant',$,IFCTEXT('Example Occupant'),$);
#700277=IFCPROPERTYSINGLEVALUE('Function',$,IFCTEXT('Work room'),$);
```

The room is an `IfcSpace` (the IFC name for a room or zone) aggregated under the level. Its geometry is an extrusion of the 4.8 by
3.8 floor outline up to 3.0 m. The properties are single values in a property set linked by `IfcRelDefinesByProperties`. `RoomId` is
`EX-001`, six characters. The room table row repeats them, and the net area 18.24 m2 equals 4.8 times 3.8.

### 3.5 The table (guide 3)

The table's geometry is defined once, as a representation map with its origin at the footprint centre and its lowest point at
z = 0, and the element is an instance of it (`IfcMappedItem`), placed at (2.6, 2.1, 0). In the item library the same table is a
separate file, `items/table.work.1600/table.work.1600.ifc`, with a description file declaring its pivot, dimensions, collision box,
side clearances, a seat anchor and placement rules.

### 3.6 The wall covering (D-30 to D-32)

The covering is a thin `IfcCovering` shell, 10 mm thick, whose back face sits exactly on the west wall's inside face (x = 0.2, the
shell runs from x = 0.2 to 0.21). It has its own colour, `#8c6f4e`, so it becomes its own entry in the finish schedule. The simpler
alternative for a whole wall is to give the wall element itself the finish colour. Support for `IfcCovering` varies, so confirm it
with the consumer before relying on it.

### 3.7 The luminaire (optional extension; B-90 to B-93)

One assembly with a housing part and an emissive part whose name ends in ` lens`. The assembly carries the declaration properties.
The emissive part's centre is at local (2.6, 2.1, 2.89). Under a profile with a frame offset, the declared position is in the
consumer's global frame, so the height gets the offset added once:

| Property | Value |
|---|---|
| `LightPositionLocal` | `2.6,2.1,2.89` (optional, for checking) |
| `LightPosition` | `2.6,2.1,14.89` (2.89 + 12.0) |
| `LightAim` | `0,0,-1` (unit length) |
| `LightType`, `LightEnergy`, `LightRangeM`, `LightSpotDeg` | `spot`, 6, 8, 78 |
| `LightColor` | `1,0.87,0.7` (warm) |
| `LightFadeBeginM`, `LightFadeLengthM` | 40, 20 |
| `LuminaireTarget` | `EX-001` |

With the luminaires extension enabled, the checker confirms that the emissive part's centre plus the offset is within the profile's
tolerance of `LightPosition`. Under the default profile (extension off) the fixture is simply a light fixture.

### 3.8 Colours and the finish schedule (guide 2)

Each (class, colour, opacity) combination needs a finish. The checker finds nine:

| Class | Colour | Opacity | Used for |
|---|---|---|---|
| `IfcWall` | `#d9d2c3` | 1.0 | all four walls (one finish) |
| `IfcSlab` | `#c9c4b8` | 1.0 | floor slab |
| `IfcSlab` | `#e8e4da` | 1.0 | roof slab, whose underside is the ceiling |
| `IfcDoor` | `#977353` | 1.0 | door leaf |
| `IfcWindow` | `#91c8d0` | 0.45 | glass |
| `IfcFurnishingElement` | `#ccbba0` | 1.0 | the table |
| `IfcCovering` | `#8c6f4e` | 1.0 | the wall covering |
| `IfcLightFixture` | `#3d4348` | 1.0 | luminaire housing |
| `IfcLightFixture` | `#fff0cf` | 1.0 | luminaire emissive part |

`finishes/finish-schedule.json` has one entry for each, and a floor rule for `Example Occupant`. The slab entries use all three face
slots: `top` for the floor, `bottom` for the ceiling, `side` for the edge.

### 3.9 The texture set (D-40 to D-50)

`finishes/textures/plaster_example/` has `albedo.png`, `normal.png`, `orm.png` and `set.json` (1024 by 1024 pixels, 2 m per tile, so
512 pixels per metre; `tintMode` `multiply`). It is made by `tools/make_sample_texture_set.py` from seamless noise with a fixed seed.
`check_texture_set.py --preview wrap.png` writes the three-by-three arrangement so you can see that the edges do not show.

### 3.10 Package, manifest and checks (guide 4)

`run_example.py` writes the check reports into `reports/`, writes `package-meta.json`, and runs `build_package.py init` then
`verify`. The final package listing:

```
example-room-1.0.0/
  manifest.json   SHA256SUMS.txt
  ifc/example-room-master.ifc
  tables/{rooms.csv,building.json}
  finishes/{finish-schedule.json,library.json,SOURCES.csv}
  finishes/textures/plaster_example/{albedo.png,normal.png,orm.png,set.json}
  items/table.work.1600/{table.work.1600.ifc,table.work.1600.item.json}
  reports/{check_ifc.json,check_texture_set.json,check_item-table.work.1600.json}
  notes/changes.md
```

Expected output of the IFC check:

```
result: PASS (0 REQUIRED failure(s), 0 RECOMMENDED warning(s)); 1 levels, 1 rooms, 1 doors,
1 windows, 1 luminaires, 216 triangles, 136 vertices, 1 furniture, 9 finishKeys
```

## 4. Things to try

* Open `example-room-master.ifc` in any IFC viewer; it is also plain text.
* Edit `tools/make_sample.py`: rename `RoomId` to `EX-0001` and check with the strict profile (too long for 7 characters, B-23).
* Move the table to (1.4, 0.3) so that it stands in the doorway (B-42). The same fault is a case in `tools/selftest.py`.
* Remove the `IfcRelFillsElement` of the door (B-41), or change the emissive part's name to end in `glow` (B-90, strict profile).
* Change `LightPosition` height to 20 and see the mismatch (B-92, strict profile).

## 5. What the example leaves out

Stairs and a second level (B-60 to B-62), a free-standing sign (B-100), reservation volumes (B-80), several rooms with a room table
of more than one row, and a library with several items. Each is a small extension of what is here; the rule text in guides 1 to 3 says how.
