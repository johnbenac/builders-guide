<!-- chunk: g4--6-pre-submission-checklist | source: 04-delivery-and-acceptance-guide.md | title: 6. Pre-submission checklist | rules: X-41 -->
## 6. Pre-submission checklist

Tick every line before sending. Lines marked R are REQUIRED rules; the others are RECOMMENDED.

**Profile and frame**
- [ ] R I know which profile I build for (or I used the default and said so) and the report names it.
- [ ] R The file is in an accepted schema edition, in metres, in the profile's frame (B-01, B-02, B-10).
- [ ] The file is in the placement the profile expects, and a `FrameNote` property says so (B-11, B-12).

**Structure**
- [ ] R Every level has a name and an elevation, and every element belongs to a level (B-13).
- [ ] R The file is ASCII only (B-04), within the limits (B-05), and every product yields triangles (B-06).
- [ ] R Every `GlobalId` is unique and stable (B-70). Entity numbers follow the profile's range when it assigns one (B-71).

**Rooms**
- [ ] R Every room is an `IfcSpace` with geometry and a flat floor (B-20, B-21).
- [ ] R `RoomId` values are unique and meet the profile (B-22, B-23); every room has one (B-26, required in profiles that say so).
- [ ] Every room has `Occupant` and `Function`, a full name, and areas and levels where known (B-24, B-25, B-27, B-28).
- [ ] Streets, paths and park areas are rooms too (B-29).
- [ ] The room table is complete (X-41).

**Fabric**
- [ ] R Doors and windows fill openings that void walls (B-41, B-44); doorways are clear (B-42).
- [ ] R Slab holes are openings (B-53); floors are slabs or sit on a floor the consumer supplies (B-50, B-51).
- [ ] R Every stair flight is an `IfcStairFlight` (B-60); every multi-level building has a stair (B-62).
- [ ] Risers and slopes are within the profile (B-61, B-64).
- [ ] Reservation volumes are marked (B-80, B-81).

**Optional extensions (only when the profile enables them)**
- [ ] R Luminaires: assemblies with housing and emissive part and all properties, in the consumer's global frame (B-90 to B-93).
- [ ] R Signboards: all properties, fitting text, honest reading distance (B-100 to B-102).
- [ ] R Walkability: free standing point in every room (B-33).

**Finishes and items**
- [ ] R Every (class, colour, opacity) combination is in the finish schedule (D-03).
- [ ] R Every texture set has its maps and `set.json` with `tileMetres` (D-40, D-41, D-43).
- [ ] I looked at the three-by-three wrap preview of every texture (D-42, D-50).
- [ ] Items are modelled to the guide: class, pivot, collision (F-01, F-21, F-40).

**Package**
- [ ] R The manifest, hashes, provenance and licences are complete; `build_package.py verify` passes (X-10 to X-21).
- [ ] R The check report is for the exact master file and the profile used, and shows no REQUIRED failure (X-40).
- [ ] The version number follows the table in section 4, and `notes/changes.md` is written (X-30 to X-32).
- [ ] `notes/open-points.md` lists anything I could not settle.

**X-41 · RECOMMENDED** - Deliver `tables/rooms.csv` with the columns `roomId`, `name`, `occupant`, `kind` (`room`, `circulation`, `observation`, `open`), `enclosed` (`yes` or `no`), `level`, `levelElevationMetres`, `floorAreaM2`, `clearHeightM`, `buildingId` and `layer`, and list every new `Occupant` string with the room-id prefix that goes with it and its kind, so a receiving party can add its rules before intake. Open areas are listed as rooms too. A starting file is in `templates/rooms.template.csv`.
