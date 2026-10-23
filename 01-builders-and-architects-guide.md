<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Guide 1: Builder's and Architect's Guide

For architects, builders and modellers who deliver buildings, public areas and their fittings as IFC files that many
different consumers (viewers, simulators, game runtimes, BIM tools, archives) can open and use.

Rule levels and the profile mechanism are explained in the [README](README.md). Every number that depends on a consumer is
a **profile parameter**, written in `backticks` like `limits.maxTriangles`; its default is in `profiles/default.json` and the
full list is in [07-profile-parameters.md](07-profile-parameters.md).

## 1. Vocabulary

| Term | Meaning |
|---|---|
| consumer | any program or person that receives your delivery and uses it: a viewer, a simulator, a game runtime, a BIM tool, an archive |
| profile | the JSON file a consumer publishes with its parameters (limits, identifier rules, optional extensions); the default profile is `profiles/default.json` |
| master file | the single coordinated IFC file for one placement area |
| level | one floor of a building: an `IfcBuildingStorey` |
| room | a named area with a floor, modelled as an `IfcSpace` (the IFC entity name; here it always means "room or zone") |
| zone | a named volume that is data only: an `IfcSpatialZone` |
| declaration property | a named property this set asks you to write because consumers read it (for example `RoomId`); a profile can rename them |
| extension | an optional group of rules a profile switches on when its consumer needs it: walkability, luminaires, signboards, furniture collision |

## 2. What the profile gives you

Before you start, get the profile of the consumer you build for. If you have none, use `profiles/default.json` and say so in
your delivery notes. If a number your work depends on is missing, ask the consumer; do not guess.

| Profile item | What it tells you | Parameters |
|---|---|---|
| frame | which way +X and +Y point, the height of your local z = 0 in the consumer's frame, whether the file is placed as authored | `frame.horizontalAxes`, `frame.levelOffsetMetres`, `frame.placement` |
| limits and budgets | hard caps and recommended sizes | `limits.*`, `budgets.*` |
| identifiers | room identifier length and pattern, assigned entity-number range, allowed occupants | `identifiers.*`, `propertyNames` |
| geometry | doorway, stair and ramp values | `geometry.*` |
| volumes | the region to stay inside, regions to keep out, floors the consumer supplies | `buildVolume`, `keepOut`, `baseSurfaces` |
| extensions | whether it walks people through rooms, turns fixtures into lights, generates signs, simplifies furniture | `extensions.*` |
| rule levels | rules it makes stricter or switches off | `ruleLevels` |

## 3. File and schema

**B-01 · REQUIRED** - Deliver an IFC schema edition the profile accepts (`schema.allowed`, default IFC4). Other editions may open in some tools, but files in an unlisted edition are not portable to that consumer.

**B-02 · REQUIRED** - Declare the length unit as metres (an `IfcSIUnit` `LENGTHUNIT` `METRE`, or a prefixed or conversion-based unit that resolves to metres) and model in it. A missing or misread unit rescales the whole building.

**B-02a · RECOMMENDED** - Prefer plain metres (a `METRE` unit with no prefix) over a prefixed or conversion-based unit, which some tools mishandle.

**B-03 · RECOMMENDED** - Deliver one coordinated master file per placement area, and send per-building files only as alternates. Several overlapping files for one area leave the consumer guessing which one is authoritative.

**B-04 · REQUIRED** - Keep the file plain ASCII: write every non-ASCII character with the format's escape (`\X2\00B7\X0\` for a middle dot, `\X2\2014\X0\` for a long dash). Raw bytes above 127 are read differently by different tools.

**B-05 · REQUIRED** - Stay within the profile's hard limits: `limits.maxFileMegabytes`, `limits.maxVertices` and `limits.maxTriangles`. A file over a consumer's cap is refused or truncated.

**B-06 · REQUIRED** - Use geometry that every common reader can display: swept solids (`IfcExtrudedAreaSolid` with rectangle, circle, arbitrary closed or arbitrary-with-voids profiles), faceted breps or polygonal face sets, and mapped items. Boolean-heavy breps, swept disks and unusual profiles are dropped by many readers without a message; `check_ifc.py` reports products that have a representation but yield no triangles.

**B-07 · RECOMMENDED** - Make the export deterministic: the same inputs give a byte-identical file (fixed timestamps, stable ordering, `GlobalId` values derived from stable keys). Consumers and reviewers compare revisions.

**B-08 · RECOMMENDED** - Write each STEP entity on a single line when the profile asks (`file.singleLineEntities`). Line-oriented tools, diff tools and simple readers handle such files; wrapped entities are valid but can be missed. A consumer that depends on it raises this rule to required.

**B-09 · RECOMMENDED** - Keep the file below the profile's recommended size, `budgets.recommendedFileMegabytes`. Large files load slowly and are hard to review.

## 4. Units, axes, origin and levels

**B-10 · REQUIRED** - Use a right-handed frame with Z up and the horizontal axes the profile states (`frame.horizontalAxes`), in metres. Models authored with another up axis come in turned over.

**B-11 · RECOMMENDED** - Author in the placement the profile expects (`frame.placement`): with `final`, local z = 0 is the finished floor of the lowest level and the consumer applies no offset or rotation, so author in the final placement frame. If you cannot, state the offset in the frame note (B-12).

**B-12 · RECOMMENDED** - State your frame in the file: a property set on the `IfcProject` with a text property `FrameNote` ("metres; +X forward; +Y left; +Z up; local z = 0 at the finished floor of the lowest level") and a number `LevelOffsetMetres`. A written note lets a reviewer or another tool verify the frame.

**B-13 · REQUIRED** - Create one `IfcBuildingStorey` for every level of every building, with a `Name` and a numeric `Elevation` equal to the level's finished-floor height in your file's frame, and make every element belong to one: contained (`IfcRelContainedInSpatialStructure`), aggregated (`IfcRelAggregates`) or, for zones, referenced (`IfcRelReferencedInSpatialStructure`). Elements without a level are dropped whenever a tool works level by level.

**B-14 · RECOMMENDED** - Use the full hierarchy `IfcProject` > `IfcSite` > `IfcBuilding` > `IfcBuildingStorey`, one `IfcBuilding` per building, and level names that start with the building name (`Clinic - ground / +0 m`).

**B-15 · RECOMMENDED** - Keep floor-to-floor heights regular so that stairs, lifts and openings line up between levels; make tall halls an exception you can name.

## 5. Rooms and zones

A room is the unit a consumer identifies, lists, lights, signs, and places people in.

**B-20 · REQUIRED** - Model every room as an `IfcSpace` (internal, `ELEMENT`) whose geometry is an upward extrusion of the room's floor outline: the lowest plane of the solid is the floor and the top is the underside of the ceiling or slab above. Tools derive the floor and area from that lowest plane, so the floor must be one flat horizontal plane.

**B-21 · REQUIRED** - Give every `IfcSpace` geometry. A room without geometry cannot be located, measured or shown.

**B-22 · REQUIRED** - Give every room that has a `RoomId` a value that is unique, and write it as an `IfcPropertySingleValue` inside an `IfcPropertySet` linked by `IfcRelDefinesByProperties`. Duplicate identifiers make every reference to a room ambiguous.

**B-23 · REQUIRED** - Make room identifiers meet the profile: at most `identifiers.roomIdMaxLength` characters and matching `identifiers.roomIdPattern`. Consumers print identifiers on labels and store them in fixed-width fields.

**B-24 · RECOMMENDED** - Give every room an `Occupant` (text): the organisation or use it belongs to. When the profile lists allowed values (`identifiers.occupants`) use one of them exactly; consumers classify rooms by this text.

**B-25 · RECOMMENDED** - Give every room a `Function` (text) describing its use. When the profile names a convention for circulation (`identifiers.circulationPrefix`), start corridors, lobbies, stair halls and streets with it.

**B-26 · RECOMMENDED** - Give every room a `RoomId`. Tools that find no identifier invent one from the room's name, and that changes when the name changes, which breaks every saved reference. A consumer that needs stable references raises this rule to required (`ruleLevels`).

**B-27 · RECOMMENDED** - Also supply, when known: `NetAreaSquareMetres` (number), `BaseLevelMetres` (number), `ClearHeightMetres` (number) and `Notes` (text). IFC's standard property set for rooms has related properties (for example `Reference` and `NetPlannedArea`); a profile may map the declaration names to those (`propertyNames`).

**B-28 · RECOMMENDED** - Give each room a complete, human-readable `Name`; names appear in lists and on labels.

**B-29 · RECOMMENDED** - Declare streets, paths, plazas and park areas as rooms too, with an identifier and a `Function`, so that they can be referred to, lit and signed. Open floor that belongs to no room has no identity.

**B-30 · RECOMMENDED** - Let rooms on one level touch along wall centre lines but not overlap by more than the wall thickness; overlapping floors make "which room is this point in" ambiguous.

**B-31 · RECOMMENDED** - Draw the room outline at the inside wall faces so the floor area is the usable area.

**B-32 · RECOMMENDED** - Group rooms into buildings with a `BuildingId` property, and mark long-lived content separately from replaceable content with a `Layer` property (`permanent` or `interim`), so that a building can be swapped without touching its surroundings.

### What a consumer typically builds from a room

| Place field | Comes from |
|---|---|
| identifier | `RoomId` (or one invented from the name when missing) |
| name, function, occupant, notes | `Name`, `Function`, `Occupant`, `Notes` |
| kind and organisation | rules on `Function`, `Occupant`, `RoomId` and `Name` |
| level | the level that holds the room |
| floor and ceiling height | lowest and highest point of the room solid |
| area | floor triangles; `NetAreaSquareMetres` when given |
| centre, bounds, floor outline | the room solid and its floor |
| doors and neighbours | the openings filled by doors (B-41) |

### Walkability extension: standing points

These two rules apply when the profile enables `extensions.walkability` (a consumer that places people or agents in rooms).

**B-33 · REQUIRED · walkability** - Leave every enclosed room a floor area where a person can stand: at least `extensions.walkability.standingClearanceMetres` clear of furniture, equipment, rails and transport elements. A room whose whole floor is within that distance of fixed objects has no usable start point.

**B-34 · RECOMMENDED · walkability** - Keep a free floor circle of `extensions.walkability.freeCircleMetres` in every room, and leave clear aisles from seating to doors.

## 6. Walls, doors, windows and openings

**B-40 · REQUIRED** - Model walls as `IfcWall` (`IfcWallStandardCase` is also read), not as generic proxies; consumers select, colour and count by class.

**B-40a · RECOMMENDED** - Use one element per maximal straight run rather than one per room edge.

**B-41 · REQUIRED** - Model every door as an `IfcDoor` that fills an `IfcOpeningElement` in the wall, linked with `IfcRelVoidsElement` (wall to opening) and `IfcRelFillsElement` (opening to door). Tools find doorways, count them and work out which rooms they connect from the opening; a door with no opening is a picture on a solid wall.

**B-42 · REQUIRED** - Keep every doorway passable: its clear height is at least `geometry.doorMinClearHeightMetres`, and nothing solid (a sill, a bar, a glazed panel, furniture) crosses the opening centre line at the heights in `geometry.doorwayProbeHeightsMetres`. A door leaf may stand open or closed in the model, but do not rely on it to block movement.

**B-43 · RECOMMENDED** - Make doorways at least `geometry.doorMinClearWidthMetres` wide.

**B-44 · REQUIRED** - Model every window as an `IfcWindow` in an `IfcOpeningElement` linked with the voids and fills relations, so the wall is cut where the window is.

**B-45 · RECOMMENDED** - Give glass a surface style with opacity below 1 (about 0.4 to 0.6), so that every consumer shows it as see-through.

**B-46 · RECOMMENDED** - Give walls their real thickness; zero-thickness walls and double walls confuse area, collision and rendering.

**B-47 · RECOMMENDED** - Make every room reachable through a doorway, an open edge or a stair from a circulation room.

**B-48 · RECOMMENDED** - Do not put a door in a floor or roof; floor apertures are slab openings (B-53).

## 7. Floors, roofs, ceilings and slab openings

**B-50 · RECOMMENDED** - Model every walkable floor, including walkable roofs, as an `IfcSlab` (`FLOOR` or `ROOF`) whose top face is the finished floor. Rooms standing on a floor the consumer supplies (`baseSurfaces`) need no slab of their own. Glass floors are slabs with a glass-like colour and opacity. A consumer that checks standing points or floor contact raises this to required.

**B-51 · RECOMMENDED** - Do not duplicate a floor the consumer already provides (`baseSurfaces`); two coplanar surfaces flicker.

**B-51a · RECOMMENDED** - Omit slabs that rest directly on a consumer-supplied floor, or make them very thin.

**B-52 · RECOMMENDED** - Give slabs a realistic thickness; very thin slabs are fine only for surface layers such as paving.

**B-53 · REQUIRED** - Cut every hole in a slab (stair wells, shafts, service drops) as an `IfcOpeningElement` linked by `IfcRelVoidsElement`, not as separate floor pieces that merely leave a gap.

**B-54 · RECOMMENDED** - Model ceilings or roofs. Many consumers draw no ceiling unless there is geometry; a room with nothing above it reads as open-topped. A ceiling is the underside of a slab or an `IfcCovering`.

**B-55 · RECOMMENDED** - Keep your own structure clear of openings in surfaces the consumer supplies (`baseSurfaces`), with the margin the profile states.

## 8. Circulation, stairs, ramps, lifts, rails

**B-60 · REQUIRED** - Model each stair flight as an `IfcStairFlight` (a parent `IfcStair` without geometry is fine). Consumers recognise stairs, and simulators build their walking surface, from the flight.

**B-61 · RECOMMENDED** - Keep risers at or below `geometry.stairRiserLimitMetres`, with a landing and head-room; avoid winding and spiral stairs unless you have checked the consumer reads them.

**B-62 · RECOMMENDED** - Give every multi-level building at least one real stair. Lifts drawn in IFC are often static solids; a stair is the one way between levels that every consumer understands.

**B-63 · RECOMMENDED** - Draw lifts as `IfcTransportElement` with `PredefinedType` `ELEVATOR`, with properties such as `Service`, `StopsMetres` and `ShaftWidthMetres`.

**B-64 · RECOMMENDED** - Keep every walked slope at or below `geometry.rampMaxSlope` (rise over run) except stairs, and give ramps a clear width at least as wide as a doorway. Model ramps as `IfcRamp` with `IfcRampFlight`, or as a sloped `IfcSlab`.

**B-65 · RECOMMENDED · walkability** - Do not leave low obstacles up to `extensions.walkability.stepHeightMetres` high (floor boxes, square-edged wedges) that a walker steps over unseen; ramp them or make them visible steps.

**B-66 · RECOMMENDED** - Model rails (`IfcRailing`) with cheap geometry: simple posts and one rail section. Rails with dense tessellation are a common cause of heavy files.

**B-67 · RECOMMENDED · walkability** - Know which classes the consumer treats as not solid (`extensions.walkability.nonSolidClasses`) and model walk-through areas with those classes or with reservation volumes (B-80); everything else may block movement.

### Clearance and size summary

| Item | Value | Where it comes from |
|---|---|---|
| doorway clear height | at least `geometry.doorMinClearHeightMetres` | B-42 |
| doorway probe heights | `geometry.doorwayProbeHeightsMetres` | B-42 |
| doorway clear width | at least `geometry.doorMinClearWidthMetres` | B-43 |
| stair riser | at most `geometry.stairRiserLimitMetres` | B-61 |
| walked ramp slope | at most `geometry.rampMaxSlope` | B-64 |
| free floor around fixed objects | `extensions.walkability.standingClearanceMetres` | B-33 |
| free floor circle in a room | `extensions.walkability.freeCircleMetres` | B-34 |

## 9. Names, identifiers, property sets and classification

**B-70 · REQUIRED** - Give every product a unique 22-character IFC `GlobalId` that does not change between exports. `GlobalId` is the key tools use to match an element across revisions and across files.

**B-71 · RECOMMENDED** - Number your IFC entities from the start the profile assigns (`identifiers.entityNumberStart`, when set) so that files from several authors can be merged without clashes.

**B-72 · RECOMMENDED** - Write declaration properties as text, number or boolean values in `IfcPropertySingleValue` entries of an `IfcPropertySet` linked by `IfcRelDefinesByProperties` on the product itself. Many readers ignore quantity sets, enumerations, tables and properties on types.

**B-73 · RECOMMENDED** - Use one descriptive property set per topic (`Pset_Declaration_Room`, ...) and put only declaration properties in it.

**B-74 · RECOMMENDED** - If your organisation uses a classification scheme, attach it with `IfcRelAssociatesClassification`. Many consumers ignore it, so never make it the only place a meaning is written.

**B-75 · RECOMMENDED** - Keep identifiers stable across revisions: an unchanged room, door or fixture keeps its `RoomId`, `GlobalId` and declaration ids. Replace an element by giving the new one a new id and retiring the old.

**B-76 · RECOMMENDED** - Give your own identifiers dotted prefixes (`arch.entrance`, `clinic.lobby`), at most 160 characters, no control characters.

## 10. Zones and reserved volumes

**B-80 · RECOMMENDED** - Declare a volume that must stay empty or must not be solid (a sight line, a clearance, a service corridor) twice: as an `IfcSpatialZone`, and (so it can be seen) as an `IfcBuildingElementProxy` with `PredefinedType` `PROVISIONFORSPACE`. That is the standard IFC way to mark a reserved provision: consumers that understand it leave the proxy out of physical models; any other proxy is a solid thing.

**B-81 · RECOMMENDED** - Give every zone a unique identifier (`ZoneId` or, if missing, its `Name`) and its own geometry; a zone without geometry cannot be shown or selected.

**B-81a · RECOMMENDED** - Always supply `ZoneId`, plus `ZoneClass` (for example `observation-sightline`) and `Requirement` (a sentence saying what must stay clear).

**B-82 · RECOMMENDED** - Use zones to record viewing intent (a downward sight line from a mezzanine); ordinary glass cannot be one-way, and who may look is a consumer decision, not a file property.

## 11. Optional extension: lighting fixtures

These rules apply when the profile enables `extensions.luminaires` (a consumer that turns declared fixtures into lights). Property names are those of the profile (`propertyNames`).

**B-90 · REQUIRED · luminaires** - Model each fixture as an `IfcElementAssembly` that aggregates two `IfcLightFixture` parts: a housing, and an emissive part whose `Name` ends in the profile's suffix (`extensions.luminaires.lensNameSuffix`). The emissive part is the one that glows.

**B-91 · REQUIRED · luminaires** - Put every property in `extensions.luminaires.requiredProperties` on the assembly, make `LuminaireId` unique, and use a `LightType` from `extensions.luminaires.lightTypes`. A fixture missing a property cannot be turned into a light.

| Property | Type | Meaning |
|---|---|---|
| `LuminaireId` | text | unique identifier |
| `LuminaireMount` | text | `pendant`, `ceiling`, `post`, `wall`, free text |
| `LightType` | text | one of the profile's light types |
| `LightEnergy` | number | strength in the consumer's units |
| `LightRangeM` | number | reach in metres |
| `LightSpotDeg` | number | cone angle in degrees |
| `LightColor` | text `"r,g,b"` | each 0 to 1 |
| `LightPosition` | text `"x,y,z"` | where the light sits, in the consumer's global frame (B-92) |
| `LightAim` | text `"x,y,z"` | unit vector the light points along |
| `LightFadeBeginM`, `LightFadeLengthM` | number | where the light starts to fade, and how long the fade is |
| `LuminaireTarget` | text, optional | the `RoomId` the fixture serves |

**B-92 · REQUIRED · luminaires** - Write `LightPosition` in the consumer's global frame: the file-local point plus `frame.levelOffsetMetres` (same x and y, z plus the offset); the geometry stays file-local. The emissive part's centre plus the offset must be within `extensions.luminaires.positionToleranceMetres` of the declared point.

**B-92a · RECOMMENDED · luminaires** - Give the file-local position as well (`LightPositionLocal`) so a reviewer can check the offset was applied once.

**B-93 · REQUIRED · luminaires** - Make `LightAim` a unit vector (length 1 within 1e-6) in the consumer's frame.

**B-94 · RECOMMENDED · luminaires** - Give every enclosed room at least one fixture (set `LuminaireTarget`), between the floor and the ceiling, in warm colours, not pointed at glazing.

**B-95 · RECOMMENDED · luminaires** - Count the lights: every declared fixture may become a real light, and the consumer may cap them per room (`extensions.luminaires.maxPerRoom`).

## 12. Optional extension: signboards

These rules apply when the profile enables `extensions.signboards` (a consumer that generates signs from declared boards).

**B-100 · REQUIRED · signboards** - Model a board as an `IfcElementAssembly` carrying every property in `extensions.signboards.requiredProperties`, with a `SignboardKind` from `extensions.signboards.kinds`.

| Property | Type | Meaning |
|---|---|---|
| `SignboardId` | text | unique identifier |
| `SignboardKind` | text | one of the profile's kinds (default `entrance_board`, `stop_board`) |
| `SignboardText`, `SignboardSub` | text | main text, optional second line |
| `SignboardWidthM`, `SignboardHeightM` | number | board size in metres |
| `SignboardReadM` | number | distance in metres from which it must be readable |
| `SignboardPosition` | text `"x,y,z"` | centre, in the consumer's global frame (B-92) |
| `SignboardNormal` | text `"x,y,z"` | unit vector pointing away from the board's face |

**B-101 · REQUIRED · signboards** - Make the main text fit the board: allow about 0.55 times the capital height of width per character plus a margin of 12 % of the board height on each side; text that cannot be fitted at a capital height of 0.05 m is an error.

**B-102 · RECOMMENDED · signboards** - Declare a reading distance your letters support: capital height in metres must be at least `pixels * readM / extensions.signboards.displayPixelsPerRadian`, with pixels from `extensions.signboards.minCapitalPixels` (primary text), and the distance within `extensions.signboards.readingDistanceMetres`.

**B-103 · RECOMMENDED · signboards** - Declare an entrance board on the wall's outer face, not the wall centre plane, and keep lamps and trees away from its face.

## 13. Geometry hygiene

**B-110 · REQUIRED** - Keep all geometry inside the profile's build volume (`buildVolume`) and outside its keep-out regions (`keepOut`), when it gives them; check every vertex, not only footprints.

**B-111 · RECOMMENDED** - Make solids closed and consistently oriented: no missing faces, no inside-out solids, no zero-area or duplicate faces.

**B-112 · RECOMMENDED** - Avoid coplanar overlapping faces (two walls sharing a face, a covering lying exactly on a wall, a slab exactly on a floor). Offset thin layers or merge them.

**B-113 · RECOMMENDED** - Use mapped items (`IfcMappedItem` with `IfcRepresentationMap`) for repeated parts. They keep files small; most consumers expand them to ordinary triangles, so they save file size, not drawing cost.

**B-114 · RECOMMENDED** - Do not model what cannot be seen or used: hidden interiors, bolts, hinge detail, text as geometry, curves with more than `geometry.maxCurveSegmentsPerCircle` segments per full circle.

**B-115 · RECOMMENDED** - Do not model terrain, soil or relief in IFC unless the profile says how. Trees and planting may be `IfcGeographicElement` markers; consumers differ on whether they are solid.

**B-116 · RECOMMENDED** - Do not model a thin layer at a height where the consumer adds its own surface layer (floor finishes laid on the room floor); two layers at one height flicker.

## 14. Level of detail and budgets

Triangle count drives load time; the number of distinct materials and objects drives drawing cost. Hard caps are `limits.*` (B-05); recommended sizes are `budgets.*`.

| Quantity | Profile parameter | Default |
|---|---|---|
| file size, hard | `limits.maxFileMegabytes` | 250 MB |
| vertices, hard | `limits.maxVertices` | 10,000,000 |
| triangles, hard | `limits.maxTriangles` | 5,000,000 |
| file size, recommended | `budgets.recommendedFileMegabytes` | 100 MB |
| triangles, recommended | `budgets.recommendedTriangles` | 1,000,000 |
| distinct (class, colour, opacity) combinations | `budgets.maxDistinctColours` | 50 |

**B-120 · RECOMMENDED** - Stay under the profile's recommended triangle count, `budgets.recommendedTriangles`. A constrained consumer publishes a much lower figure; build to the profile you were given.

**B-121 · RECOMMENDED** - Spend triangles where the viewer looks: entrances, interiors a person stands in, anything within arm's reach. Distant detail is wasted.

## 15. What to avoid

* A floor that duplicates one the consumer supplies (B-51).
* Doors without openings, or openings without doors (B-41).
* Anything across a doorway (B-42).
* Rooms without identifiers or with duplicates (B-22, B-26).
* Heavily tessellated rails and balusters (B-66).
* Low steps and ledges nobody can see (B-65, with the walkability extension).
* A proxy used for something that must be walk-through; use a reservation volume (B-80).
* Missing ceilings (B-54).
* Elements outside any level (B-13).
* Geometry readers drop silently (B-06).
* One-way glass promises: ordinary glass is two-way.
* Changing identifiers between revisions (B-75).
