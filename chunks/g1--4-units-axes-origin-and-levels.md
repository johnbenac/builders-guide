<!-- chunk: g1--4-units-axes-origin-and-levels | source: 01-builders-and-architects-guide.md | title: 4. Units, axes, origin and levels | rules: B-10,B-11,B-12,B-13,B-14,B-15 -->
## 4. Units, axes, origin and levels

**B-10 · REQUIRED** - Use a right-handed frame with Z up and the horizontal axes the profile states (`frame.horizontalAxes`), in metres. Models authored with another up axis come in turned over.

**B-11 · RECOMMENDED** - Author in the placement the profile expects (`frame.placement`): with `final`, local z = 0 is the finished floor of the lowest level and the consumer applies no offset or rotation, so author in the final placement frame. If you cannot, state the offset in the frame note (B-12).

**B-12 · RECOMMENDED** - State your frame in the file: a property set on the `IfcProject` with a text property `FrameNote` ("metres; +X forward; +Y left; +Z up; local z = 0 at the finished floor of the lowest level") and a number `LevelOffsetMetres`. A written note lets a reviewer or another tool verify the frame.

**B-13 · REQUIRED** - Create one `IfcBuildingStorey` for every level of every building, with a `Name` and a numeric `Elevation` equal to the level's finished-floor height in your file's frame, and make every element belong to one: contained (`IfcRelContainedInSpatialStructure`), aggregated (`IfcRelAggregates`) or, for zones, referenced (`IfcRelReferencedInSpatialStructure`). Elements without a level are dropped whenever a tool works level by level.

**B-14 · RECOMMENDED** - Use the full hierarchy `IfcProject` > `IfcSite` > `IfcBuilding` > `IfcBuildingStorey`, one `IfcBuilding` per building, and level names that start with the building name (`Clinic - ground / +0 m`).

**B-15 · RECOMMENDED** - Keep floor-to-floor heights regular so that stairs, lifts and openings line up between levels; make tall halls an exception you can name.
