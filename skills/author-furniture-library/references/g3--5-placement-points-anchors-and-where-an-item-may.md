<!-- chunk: g3--5-placement-points-anchors-and-where-an-item-may | source: 03-furniture-and-fixtures-guide.md | title: 5. Placement points, anchors and where an item may be placed | rules: F-30,F-31,F-32,F-33,F-34 -->
## 5. Placement points, anchors and where an item may be placed

Most consumers ignore this data; it lets a placement tool, or a different consumer, place items without a person.

**F-30 · RECOMMENDED** - Declare anchors in item coordinates (metres, relative to the pivot). Anchor `kind` values: `seat` (where a person sits; direction = the way they face), `surface` (a usable top), `reach` (where a person stands to use it), `storage`, `power`, `door-swing` (a volume to keep clear), `mount` (where it attaches). Give each anchor an `id` unique within the item.

**F-31 · RECOMMENDED** - Declare placement rules under `placement`: `mounting` (`floor`, `wall`, `ceiling`, `surface`), `againstWall`, `minWallDistance` (metres), `rotations` (allowed turns about the vertical axis, in degrees), `roomUses` (kinds of use it suits, free words matching the `Function` text of rooms), `avoid` (kinds of room it must not go in), and `mountHeight` for wall items.

**F-32 · RECOMMENDED** - Declare clearance minimums around the item: `front`, `back`, `left`, `right`, `top` (metres of free volume needed). As a guide: the profile's standing clearance on each side (`extensions.walkability.standingClearanceMetres`) and enough free floor in front of anything a person uses to reach it and pass. Keep aisles from seating to doors free.

**F-33 · RECOMMENDED** - Keep items off door openings and off the floor directly in front of a door; a table in the doorway fails the doorway check (guide 1, B-42).

**F-34 · RECOMMENDED** - Do not place items so that they cover a room's whole free floor (guide 1, B-33).
