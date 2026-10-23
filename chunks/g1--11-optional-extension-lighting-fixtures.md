<!-- chunk: g1--11-optional-extension-lighting-fixtures | source: 01-builders-and-architects-guide.md | title: 11. Optional extension: lighting fixtures | rules: B-90,B-91,B-92,B-92a,B-93,B-94,B-95 -->
## 11. Optional extension: lighting fixtures

These rules apply when the profile enables `extensions.luminaires` (a consumer that turns declared fixtures into lights). Property names are those of the profile (`propertyNames`).

**B-90 · REQUIRED · luminaires** - Model each fixture as an `IfcElementAssembly` that aggregates two `IfcLightFixture` parts: a housing, and an emissive part whose `Name` ends in the profile's suffix (`extensions.luminaires.lensNameSuffix`). The emissive part is the one that glows.

**B-91 · REQUIRED · luminaires** - Put every property in `extensions.luminaires.requiredProperties` on the assembly, make `LuminaireId` unique, and use a `LightType` from `extensions.luminaires.lightTypes`. A fixture missing a property cannot be turned into a light.

| Property | Type | Meaning |
|---|---|---|
| `LuminaireId` | text | unique identifier |
| `LuminaireMount` | text | `pendant`, `ceiling`, `post`, `wall`, free text |
| `LightType` | text | one of the profile's light types |
| `LightEnergy` | number | strength in the consumer's units |
| `LightRangeM` | number | reach in metres |
| `LightSpotDeg` | number | cone angle in degrees |
| `LightColor` | text `"r,g,b"` | each 0 to 1 |
| `LightPosition` | text `"x,y,z"` | where the light sits, in the consumer's global frame (B-92) |
| `LightAim` | text `"x,y,z"` | unit vector the light points along |
| `LightFadeBeginM`, `LightFadeLengthM` | number | where the light starts to fade, and how long the fade is |
| `LuminaireTarget` | text, optional | the `RoomId` the fixture serves |

**B-92 · REQUIRED · luminaires** - Write `LightPosition` in the consumer's global frame: the file-local point plus `frame.levelOffsetMetres` (same x and y, z plus the offset); the geometry stays file-local. The emissive part's centre plus the offset must be within `extensions.luminaires.positionToleranceMetres` of the declared point.

**B-92a · RECOMMENDED · luminaires** - Give the file-local position as well (`LightPositionLocal`) so a reviewer can check the offset was applied once.

**B-93 · REQUIRED · luminaires** - Make `LightAim` a unit vector (length 1 within 1e-6) in the consumer's frame.

**B-94 · RECOMMENDED · luminaires** - Give every enclosed room at least one fixture (set `LuminaireTarget`), between the floor and the ceiling, in warm colours, not pointed at glazing.

**B-95 · RECOMMENDED · luminaires** - Count the lights: every declared fixture may become a real light, and the consumer may cap them per room (`extensions.luminaires.maxPerRoom`).
