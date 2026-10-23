<!-- chunk: g3--8-variants-and-instancing | source: 03-furniture-and-fixtures-guide.md | title: 8. Variants and instancing | rules: F-60,F-61,F-62,F-62a,F-63 -->
## 8. Variants and instancing

**F-60 · RECOMMENDED** - Describe variants in the description file. A variant is a finish variant (a different colour; same item id, same geometry), a size variant (a different item id) or an option (different geometry, also a different id).

**F-61 · RECOMMENDED** - Place repeated items as instances: each instance is an element of its own (own `GlobalId`, own `ObjectPlacement`), sharing geometry through `IfcMappedItem` and `IfcRepresentationMap`. Rotate instances about the vertical axis only.

**F-62 · REQUIRED** - Give each instance its own unique `GlobalId` (guide 1, B-70) and a level to belong to (guide 1, B-13).

**F-62a · RECOMMENDED** - Place every instance inside the room it serves, and do not let it extend through a wall or a floor.

**F-63 · RECOMMENDED** - Record the item id and version on every instance (`ItemId`, `ItemVersion`, F-03) so that a revision of the library can be rolled out by replacing instances.
