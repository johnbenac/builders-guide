<!-- chunk: g3--3-item-library-format | source: 03-furniture-and-fixtures-guide.md | title: 3. Item library format | rules: F-10,F-11,F-12 -->
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
