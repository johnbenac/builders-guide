<!-- chunk: params--introduction-part-3-of-3 | source: 07-profile-parameters.md | title: Introduction (part 3 of 3) | rules: - -->
| Parameter | Meaning | default | strict | Rules |
|---|---|---|---|---|
| `extensions.signboards.kinds` | allowed values of SignboardKind | `["entrance_board", "stop_board"]` | `["entrance_board", "stop_board"]` | B-100 |
| `extensions.signboards.requiredProperties` | properties every board must carry | `["SignboardId", "SignboardKind", "SignboardText", "Signbo...` | `["SignboardId", "SignboardKind", "SignboardText", "Signbo...` | B-100 |
| `extensions.signboards.displayPixelsPerRadian` | pixels per radian of the display, used for legibility | `1000` | `1090` | B-102 |
| `extensions.signboards.minCapitalPixels` | smallest capital height in pixels for primary, secondary and tertiary text | `{"primary": 16, "secondary": 12, "tertiary": 9}` | `{"primary": 16, "secondary": 12, "tertiary": 9}` | B-102 |
| `extensions.signboards.readingDistanceMetres` | smallest and largest accepted reading distance | `[5, 18]` | `[5, 18]` | B-102 |
| `extensions.furnitureCollision.enabled` | consumer approximates furniture with a simple collider | `false` | `true` | - |
| `extensions.furnitureCollision.mode` | box: one axis-aligned box per furniture element; mesh: exact triangles | `"box"` | `"box"` | F-40 |
| `textures.sizesPixels` | allowed texture map sizes in pixels (square) | `[512, 1024, 2048]` | `[1024]` | D-44 |
| `textures.densityPixelsPerMetre` | smallest and largest texel density | `[250, 2500]` | `[340, 2050]` | D-45 |
| `textures.maps` | map file names a set must contain, without extension | `["albedo", "normal", "orm"]` | `["albedo", "normal", "orm"]` | D-40, D-41 |
| `textures.normalConvention` | +Y: green channel points up (OpenGL style); -Y: green points down (DirectX style) | `"+Y"` | `"+Y"` | D-41 |
| `textures.tintModes` | allowed values of tintMode in set.json | `["multiply", "authored"]` | `["multiply", "authored"]` | D-47 |
| `package.maxPackageMegabytes` | upload size cap of a whole package, or null | `null` | `500` | X-14 |
| `package.requireProvenance` | every asset needs a provenance entry | `true` | `true` | X-20 |
| `package.requireLicence` | every asset and the package need a licence | `true` | `true` | X-21 |
