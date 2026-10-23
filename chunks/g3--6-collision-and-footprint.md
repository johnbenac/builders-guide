<!-- chunk: g3--6-collision-and-footprint | source: 03-furniture-and-fixtures-guide.md | title: 6. Collision and footprint | rules: F-40,F-41,F-42,F-43,F-44 -->
## 6. Collision and footprint

**F-40 · REQUIRED · furnitureCollision** - Assume the profile's collision mode (`extensions.furnitureCollision.mode`). With `box`, the consumer builds a single axis-aligned box around the whole element after placement: if that box fits badly (an L-shaped sofa, a corner desk) deliver several box-like elements instead of one. If exact shape matters (a sloped ramp, a stepped plinth) use an `IfcBuildingElementProxy`.

**F-41 · RECOMMENDED · furnitureCollision** - Place furniture with rotations in multiples of 90 degrees where you can; a box around a 45-degree table is larger than the table.

**F-42 · RECOMMENDED** - Declare the footprint polygon and the collision box in the description (section 3.1), so a checker and a human can see what a consumer will do.

**F-43 · RECOMMENDED · furnitureCollision** - Never make an item that must be walked under, through or between (an open pergola, a chair with gaps between its legs); in `box` mode it is a solid block.

**F-44 · RECOMMENDED · walkability** - Avoid low obstacles up to `extensions.walkability.stepHeightMetres` that are not obviously steps (a floor box, a cable cover): a walker steps over them unnoticed.
