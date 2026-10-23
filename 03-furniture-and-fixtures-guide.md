<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Guide 3: Furniture and Fixtures Guide

For designers who deliver furniture, equipment, fixtures and accents as reusable items that can be placed in any compatible
consumer.

Rule levels and the profile mechanism are explained in the [README](README.md); profile parameters appear in `backticks`
(full list: [07-profile-parameters.md](07-profile-parameters.md)). Read sections 1 to 4 and 14 of guide 1 first, and section 1
of guide 2.

## 1. What consumers do with an item

An item reaches a consumer as an element inside a building's master IFC file. What happens next differs, but these things are common:

| Stage | What typically happens | Consequence for you |
|---|---|---|
| Reading | the class of the element and its geometry are read; declaration properties are read by name | use the right class (section 2) |
| Material | class, colour and opacity select a finish (guide 2) | distinct finish, distinct colour |
| Collision | furniture is approximated by a simple shape, often **one axis-aligned box** around the element, while fixed equipment may collide as exact triangles | a chair can be a solid block; do not rely on walking under a table. The profile states the mode (`extensions.furnitureCollision`) |
| Standing points | simulators keep a start point clear of furniture by a margin | leave free floor (guide 1, B-33, with the walkability extension) |
| Interaction | most consumers have no sit points, drawers or moving parts for IFC items | item data beyond the model is for placement tools |

An **item library** is a folder of single-item IFC files plus a description file per item. A building author places items into
the master file as instances (section 8).

## 2. Classes and categories

**F-01 · REQUIRED** - Use these classes for items, because consumers and tools are written for them, and make the description's class agree with the model.

| Item kind | IFC class | Typical consumer treatment |
|---|---|---|
| movable furniture (tables, chairs, benches, beds, shelves, sofas) | `IfcFurnishingElement` | simple shape or box; the default choice |
| fixed equipment, built-in units, counters, anything where the exact solid shape matters | `IfcBuildingElementProxy` (`PredefinedType` `USERDEFINED`, `ObjectType` set) | exact triangle mesh |
| light fixtures | `IfcElementAssembly` of two `IfcLightFixture` parts | see guide 1, section 11 |
| signs and boards | `IfcElementAssembly` | see guide 1, section 12 |
| rails and guards | `IfcRailing` | cheap geometry (guide 1, B-66) |
| lifts | `IfcTransportElement` (`ELEVATOR`) | usually static (guide 1, B-63) |

Other classes are drawn but get no special treatment; ask before using them for items.

**F-02 · RECOMMENDED** - Set `ObjectType` to a category word from this list so that reports and schedules can group items: `table`, `desk`, `seat`, `bench`, `sofa`, `bed`, `shelf`, `cabinet`, `counter`, `partition`, `planter`, `equipment`, `appliance`, `lamp`, `sign`, `accent`, `other`.

**F-03 · RECOMMENDED** - Add a property set `Pset_Declaration_Item` with text properties `ItemId` (the library id, section 3), `ItemVersion` (SemVer), `Role` (what the item is for, for example `work table`), and optionally `Occupant` and `PlanningStatus`.

## 3. Item library format

One item is one folder.

```
library/
  library.manifest.json          the package manifest (guide 4)
  items/
    table.work.1600/
      table.work.1600.ifc        one IfcFurnishingElement at the origin
      table.work.1600.item.json  the description (section 3.1)
      preview.png                optional, 512 by 512
  finishes/                      optional: finish schedule and texture sets (guide 2)
```

**F-10 · RECOMMENDED** - Make each item file IFC4 (guide 1, B-01 to B-06) containing exactly one furniture or equipment element, placed at the origin with no rotation, in metres, with a stable `GlobalId`. The item file needs a project, the length unit and a geometric context, but no building, levels or rooms.

**F-11 · RECOMMENDED** - Give every item a library id of the form `category.name.size` in lower case (for example `seat.stool.450`), unique within the library and never reused for a different design. The folder, the files, `ItemId` and the description all use the same id.

**F-12 · RECOMMENDED** - Provide a description file `<ItemId>.item.json` for every item (section 3.1). The checker and reviewers use it; schema: `schemas/item.schema.json`.

### 3.1 The description file

```json
{
  "format": "item/1",
  "itemId": "table.work.1600",
  "version": "1.0.0",
  "name": "Work table, 1.6 m",
  "category": "table",
  "class": "IfcFurnishingElement",
  "pivot": { "kind": "floor", "description": "centre of the footprint, on the floor" },
  "front": [1, 0, 0],
  "dimensions": { "x": 1.6, "y": 0.8, "z": 0.74 },
  "footprint": [[-0.8, -0.4], [0.8, -0.4], [0.8, 0.4], [-0.8, 0.4]],
  "collision": { "kind": "box", "min": [-0.8, -0.4, 0.0], "max": [0.8, 0.4, 0.74] },
  "clearance": { "front": 0.9, "back": 0.0, "left": 0.45, "right": 0.45, "top": 0.0 },
  "anchors": [
    { "id": "seat-1", "kind": "seat", "position": [0.0, -0.7, 0.45], "direction": [0, 1, 0] },
    { "id": "work-surface", "kind": "surface", "position": [0.0, 0.0, 0.74], "direction": [0, 0, 1] }
  ],
  "placement": {
    "mounting": "floor",
    "againstWall": false,
    "rotations": [0, 90, 180, 270],
    "roomUses": ["work", "meeting", "study"],
    "avoid": ["circulation"],
    "minWallDistance": 0.0
  },
  "variants": [
    { "id": "oak", "colour": "#ccbba0", "finish": "furniture.oak.veneer" }
  ],
  "budget": { "triangles": 12, "textures": 0 },
  "provenance": { "author": "organisation name", "licence": "stated licence", "source": "original" }
}
```

## 4. Dimensions, origin and pivot

**F-20 · REQUIRED** - Model in metres in the right-handed frame of guide 1 (B-02, B-10), with the item's own origin at its pivot (F-21).

**F-20a · RECOMMENDED** - Do not scale an item with an `IfcCartesianTransformationOperator` or any non-unit transform. Model it at its real size so that what you measure is what is drawn.

**F-21 · RECOMMENDED** - Put the pivot where the item meets the building, so placing it needs one point and one turn.

| Mounting | Pivot (origin) | Local axes |
|---|---|---|
| `floor` | centre of the footprint, on the floor (lowest point at z = 0) | +X is the front (the side a user faces and the side that needs clear floor), +Z up |
| `wall` | centre of the back face, at the mounting height in `placement.mountHeight` | +X is the front, pointing away from the wall |
| `ceiling` | centre of the fixing plane (the top of the item) | +Z stays up; the item hangs below the origin, so its dimensions run to negative z |
| `surface` | centre of the contact area on the thing it stands on | +X is the front |

**F-22 · RECOMMENDED** - Declare the bounding dimensions in the description and keep them equal (within 1 cm) to the measured size of the geometry.

**F-23 · RECOMMENDED** - Use true-to-life sizes: a work table is about 1.6 by 0.8 by 0.74 m, a chair about 0.5 by 0.55 by 0.85 m. Consumers do not scale items.

## 5. Placement points, anchors and where an item may be placed

Most consumers ignore this data; it lets a placement tool, or a different consumer, place items without a person.

**F-30 · RECOMMENDED** - Declare anchors in item coordinates (metres, relative to the pivot). Anchor `kind` values: `seat` (where a person sits; direction = the way they face), `surface` (a usable top), `reach` (where a person stands to use it), `storage`, `power`, `door-swing` (a volume to keep clear), `mount` (where it attaches). Give each anchor an `id` unique within the item.

**F-31 · RECOMMENDED** - Declare placement rules under `placement`: `mounting` (`floor`, `wall`, `ceiling`, `surface`), `againstWall`, `minWallDistance` (metres), `rotations` (allowed turns about the vertical axis, in degrees), `roomUses` (kinds of use it suits, free words matching the `Function` text of rooms), `avoid` (kinds of room it must not go in), and `mountHeight` for wall items.

**F-32 · RECOMMENDED** - Declare clearance minimums around the item: `front`, `back`, `left`, `right`, `top` (metres of free volume needed). As a guide: the profile's standing clearance on each side (`extensions.walkability.standingClearanceMetres`) and enough free floor in front of anything a person uses to reach it and pass. Keep aisles from seating to doors free.

**F-33 · RECOMMENDED** - Keep items off door openings and off the floor directly in front of a door; a table in the doorway fails the doorway check (guide 1, B-42).

**F-34 · RECOMMENDED** - Do not place items so that they cover a room's whole free floor (guide 1, B-33).

## 6. Collision and footprint

**F-40 · REQUIRED · furnitureCollision** - Assume the profile's collision mode (`extensions.furnitureCollision.mode`). With `box`, the consumer builds a single axis-aligned box around the whole element after placement: if that box fits badly (an L-shaped sofa, a corner desk) deliver several box-like elements instead of one. If exact shape matters (a sloped ramp, a stepped plinth) use an `IfcBuildingElementProxy`.

**F-41 · RECOMMENDED · furnitureCollision** - Place furniture with rotations in multiples of 90 degrees where you can; a box around a 45-degree table is larger than the table.

**F-42 · RECOMMENDED** - Declare the footprint polygon and the collision box in the description (section 3.1), so a checker and a human can see what a consumer will do.

**F-43 · RECOMMENDED · furnitureCollision** - Never make an item that must be walked under, through or between (an open pergola, a chair with gaps between its legs); in `box` mode it is a solid block.

**F-44 · RECOMMENDED · walkability** - Avoid low obstacles up to `extensions.walkability.stepHeightMetres` that are not obviously steps (a floor box, a cable cover): a walker steps over them unnoticed.

## 7. Polygon and texture budgets

**F-50 · REQUIRED** - Stay within the profile's limits for a whole delivery: `limits.maxFileMegabytes`, `limits.maxVertices`, `limits.maxTriangles`.

**F-51 · RECOMMENDED** - Keep each item small: at most `budgets.maxItemTriangles` triangles (default 2,000), far fewer for ordinary items. Do not model hidden undersides, fasteners or text.

**F-52 · RECOMMENDED** - Do not deliver textures with an item. Items take their look from the building's finish schedule (guide 2), keyed by class and colour. If a bespoke texture set is unavoidable, deliver it as a normal texture set (guide 2, section 4) and list it in the item description.

**F-53 · RECOMMENDED** - Use one or two surface colours on an ordinary item and up to four on a feature item; every distinct colour of every item adds a material.

## 8. Variants and instancing

**F-60 · RECOMMENDED** - Describe variants in the description file. A variant is a finish variant (a different colour; same item id, same geometry), a size variant (a different item id) or an option (different geometry, also a different id).

**F-61 · RECOMMENDED** - Place repeated items as instances: each instance is an element of its own (own `GlobalId`, own `ObjectPlacement`), sharing geometry through `IfcMappedItem` and `IfcRepresentationMap`. Rotate instances about the vertical axis only.

**F-62 · REQUIRED** - Give each instance its own unique `GlobalId` (guide 1, B-70) and a level to belong to (guide 1, B-13).

**F-62a · RECOMMENDED** - Place every instance inside the room it serves, and do not let it extend through a wall or a floor.

**F-63 · RECOMMENDED** - Record the item id and version on every instance (`ItemId`, `ItemVersion`, F-03) so that a revision of the library can be rolled out by replacing instances.

## 9. Fixtures

**F-70 · REQUIRED · luminaires** - Follow guide 1 exactly for light fixtures (section 11) and, when signboards are enabled, for signs (section 12). The declaration properties are read by name, and a missing required one makes the fixture unusable.

**F-71 · RECOMMENDED · luminaires** - Make a fixture's housing and emissive part separate parts so that only the emissive part glows. Keep it a simple disc or box, give the housing a dark neutral colour and the emissive part a warm off-white.

**F-72 · RECOMMENDED** - Other fixtures (hand rails, handles, hooks, bathroom fittings, planters) are small elements with their own colour, in the classes of section 2. Do not model plumbing or wiring.

## 10. What to avoid

* Rotated or L-shaped single elements that make a wasteful box (F-40, F-41).
* Items you can walk under, through or between (F-43).
* Low ledges and floor boxes that a walker steps over unseen (F-44).
* A table or shelf in front of a door or in an aisle (F-32, F-33).
* Per-item textures (F-52).
* Many near-identical colours across items (guide 2, D-01, D-05).
* Scaled instances (F-20a).
* Items that rely on moving parts, opening doors or drawers, or on sit points the consumer does not have.
* Hidden or tiny detail that costs triangles (F-51).
