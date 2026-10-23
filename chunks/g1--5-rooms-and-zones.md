<!-- chunk: g1--5-rooms-and-zones | source: 01-builders-and-architects-guide.md | title: 5. Rooms and zones | rules: B-143,B-20,B-21,B-22,B-23,B-24,B-25,B-26,B-27,B-28,B-29,B-30,B-31,B-32,B-33,B-34 -->
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

**B-143 · RECOMMENDED** - Model an open-air room (terrace, courtyard, deck, path, plaza) as an `IfcSpace` with `PredefinedType` `EXTERNAL` and the boolean property `Enclosed` set to false, and an internal room with `Enclosed` true or absent. Its volume rises to what covers it, or to a nominal height where it is open to the sky. Consumers that look for enclosed rooms (lighting, walkability, ceilings) skip open-air rooms.

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
