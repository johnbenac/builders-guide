<!-- chunk: g3--4-dimensions-origin-and-pivot | source: 03-furniture-and-fixtures-guide.md | title: 4. Dimensions, origin and pivot | rules: F-20,F-20a,F-21,F-22,F-23 -->
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
