<!-- chunk: params--introduction-part-3-of-3 | source: 07-profile-parameters.md | title: Introduction (part 3 of 3) | rules: - -->
| Parameter | Meaning | default | strict | Rules |
|---|---|---|---|---|
| `extensions.luminaires.maxPerRoom` | most fixtures per room, or null | `null` | `16` | B-95 |
| `extensions.signboards.enabled` | consumer generates signs from declared boards | `false` | `true` | - |
| `extensions.signboards.kinds` | allowed values of SignboardKind | `["entrance_board", "stop_board"]` | `["entrance_board", "stop_board"]` | B-100 |
| `extensions.signboards.requiredProperties` | properties every board must carry | `["SignboardId", "SignboardKind", "SignboardText", "Signbo...` | `["SignboardId", "SignboardKind", "SignboardText", "Signbo...` | B-100 |
| `extensions.signboards.displayPixelsPerRadian` | pixels per radian of the display, used for legibility | `1000` | `1090` | B-102 |
| `extensions.signboards.minCapitalPixels` | smallest capital height in pixels for primary, secondary and tertiary text | `{"primary": 16, "secondary": 12, "tertiary": 9}` | `{"primary": 16, "secondary": 12, "tertiary": 9}` | B-102 |
| `extensions.signboards.readingDistanceMetres` | smallest and largest accepted reading distance | `[5, 18]` | `[5, 18]` | B-102 |
| `extensions.furnitureCollision.enabled` | consumer approximates furniture with a simple collider | `false` | `true` | - |
| `extensions.furnitureCollision.mode` | box: one axis-aligned box per furniture element; mesh: exact triangles | `"box"` | `"box"` | F-40 |
| `extensions.terrain.enabled` | consumer supplies terrain from its own source and wants a derived, read-only terrain patch in the file | `false` | `false` | - |
| `extensions.terrain.crsName` | name of the consumer's site coordinate reference system, written as the IfcProjectedCRS name; it need not be a registry code; null accepts any non-empty name | `null` | `null` | B-133 |
| `extensions.terrain.patchFormat` | form of the height patch the consumer's terrain source delivers | `"geotiff-float32-metres"` | `"geotiff-float32-metres"` | - |
| `extensions.terrain.maxErrorBoundMetres` | largest vertical difference allowed between the terrain triangles and the source samples | `0.05` | `0.05` | B-137 |
| `extensions.terrain.footprintMarginMetres` | margin by which the terrain patch must extend beyond the building footprint in plan | `10.0` | `10.0` | B-132 |
| `extensions.terrain.clearingMarginMetres` | margin round the footprint in which the terrain source clears vegetation | `2.0` | `2.0` | - |
| `extensions.terrain.grading` | grading rule sent to the terrain source: maxCutFillSlope is the steepest cut or fill slope as horizontal:vertical text, for example 1:2 | `{"maxCutFillSlope": "1:2"}` | `{"maxCutFillSlope": "1:2"}` | - |
| `extensions.terrain.seaLevelMetres` | height of sea level in the consumer's vertical datum; terrain below it is seabed | `0.0` | `0.0` | B-135 |
| `extensions.terrain.floatToleranceMetres` | how far the lowest finished floor may stand above the terrain at every footprint point before the building counts as floating | `0.5` | `0.5` | B-136 |
| `extensions.terrain.buryToleranceMetres` | how far the lowest finished floor may stand below the terrain at every footprint point before the building counts as buried | `0.5` | `0.5` | B-136 |
| `extensions.terrain.siteElevationToleranceMetres` | largest difference between IfcSite.RefElevation and the terrain height at the building origin | `0.1` | `0.1` | B-134 |
| `extensions.terrain.maxTriangles` | most triangles in the terrain element | `200000` | `200000` | B-138 |
| `textures.sizesPixels` | allowed texture map sizes in pixels (square) | `[512, 1024, 2048]` | `[1024]` | D-44 |
| `textures.densityPixelsPerMetre` | smallest and largest texel density | `[250, 2500]` | `[340, 2050]` | D-45 |
| `textures.maps` | map file names a set must contain, without extension | `["albedo", "normal", "orm"]` | `["albedo", "normal", "orm"]` | D-40, D-41 |
| `textures.normalConvention` | +Y: green channel points up (OpenGL style); -Y: green points down (DirectX style) | `"+Y"` | `"+Y"` | D-41 |
| `textures.tintModes` | allowed values of tintMode in set.json | `["multiply", "authored"]` | `["multiply", "authored"]` | D-47 |
| `package.maxPackageMegabytes` | upload size cap of a whole package, or null | `null` | `500` | X-14 |
| `package.requireProvenance` | every asset needs a provenance entry | `true` | `true` | X-20 |
| `package.requireLicence` | every asset and the package need a licence | `true` | `true` | X-21 |
