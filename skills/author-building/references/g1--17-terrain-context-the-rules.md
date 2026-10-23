<!-- chunk: g1--17-terrain-context-the-rules | source: 01-builders-and-architects-guide.md | title: 17. Terrain context: the rules | rules: B-130,B-131,B-132,B-133,B-134,B-135,B-136,B-137,B-138,B-139,B-140 -->
## 17. Terrain context: the rules

These rules apply when `extensions.terrain.enabled` is true (section 16 explains the flow and the frames).

**B-130 · REQUIRED · terrain** - Deliver the terrain as exactly one `IfcGeographicElement` with `PredefinedType` `TERRAIN`, contained in the `IfcSite`, whose body is one `IfcTriangulatedFaceSet`. It is derived, read-only context: do not edit its heights, and do not cut pads, cuts, fills or building features into it. The terrain source does grading and clearing before it cuts the patch, so the world and the model agree.

**B-131 · REQUIRED · terrain** - Make the terrain a valid heightfield over a rectangular patch: every triangle faces up and has area, no edge belongs to more than two triangles, and the triangles cover the patch rectangle exactly once. Consumers sample the surface by plan position, so an overhang, a hole or an overlap gives two heights or none for one point.

**B-132 · REQUIRED · terrain** - Make the terrain cover the building: the plan points of the lowest level's slabs and walls, grown by `extensions.terrain.footprintMarginMetres`, lie inside the patch. A patch that stops short of the footprint cannot answer where the ground is under the building.

**B-133 · REQUIRED · terrain** - Georeference the file with an `IfcMapConversion` from the model context to an `IfcProjectedCRS` named `extensions.terrain.crsName`, in metres, with the local X axis pointing east, scale 1 and `OrthogonalHeight` equal to the height above sea level of the lowest finished floor (local z = 0). The name need not be a registry code. The profile's `frame.levelOffsetMetres` must be 0, because the floor height is carried here and not by an offset.

**B-134 · REQUIRED · terrain** - Set `IfcSite.RefElevation` to the terrain height at the building origin above sea level, within `extensions.terrain.siteElevationToleranceMetres` of the terrain element at that point. The site elevation and the terrain must tell one story about where the ground is.

**B-135 · REQUIRED · terrain** - Do not put a building in water: the terrain at every footprint point of the lowest level is at or above `extensions.terrain.seaLevelMetres`, and `FootprintInWater` is not true. Terrain below sea level is seabed.

**B-136 · REQUIRED · terrain** - Do not let the building float or sink: the lowest finished floor is not above the terrain by more than `extensions.terrain.floatToleranceMetres` at every footprint point, and not below it by more than `extensions.terrain.buryToleranceMetres` at every footprint point. A house on a slope may stand above the ground at one edge and below it at another; that is allowed. A building above or below the ground everywhere was placed at the wrong height.

**B-137 · REQUIRED · terrain** - Pin the terrain source in a property set `Pset_Declaration_Terrain` on the terrain element: `Role` (`derived-context`), `PackageName`, `PackageVersion`, `PackageSha256`, `PatchSha256`, `PatchLevel`, `PixelSizeMetres`, `ErrorBoundMetres` (at most `extensions.terrain.maxErrorBoundMetres`), `Frame` and `VerticalDatum`. Heights near water can change between source versions, so a delivery says exactly which version it was built on and never carries numbers from an earlier one.

**B-138 · RECOMMENDED · terrain** - Keep the terrain within `extensions.terrain.maxTriangles`. Terrain triangles do not count against `budgets.recommendedTriangles`; they still count against the hard limits of B-05.

**B-139 · RECOMMENDED · terrain** - Keep water out of the file and declare it as metadata in `Pset_Declaration_Site` on the `IfcSite`: `SeaLevelMetres`, `FootprintInWater` and, when known, `DistanceToShoreMetres`. Sea and shoreline belong to the terrain source; the file only says how the building relates to them.

**B-140 · RECOMMENDED · terrain** - State the frame of the terrain numbers: `Pset_Declaration_Terrain.Frame` says that the file frame is x east, y north, z up and relative to the lowest finished floor. Never write coordinates in a consumer's runtime frame.
