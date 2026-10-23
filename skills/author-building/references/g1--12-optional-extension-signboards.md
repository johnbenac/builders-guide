<!-- chunk: g1--12-optional-extension-signboards | source: 01-builders-and-architects-guide.md | title: 12. Optional extension: signboards | rules: B-100,B-101,B-102,B-103 -->
## 12. Optional extension: signboards

These rules apply when the profile enables `extensions.signboards` (a consumer that generates signs from declared boards).

**B-100 · REQUIRED · signboards** - Model a board as an `IfcElementAssembly` carrying every property in `extensions.signboards.requiredProperties`, with a `SignboardKind` from `extensions.signboards.kinds`.

| Property | Type | Meaning |
|---|---|---|
| `SignboardId` | text | unique identifier |
| `SignboardKind` | text | one of the profile's kinds (default `entrance_board`, `stop_board`) |
| `SignboardText`, `SignboardSub` | text | main text, optional second line |
| `SignboardWidthM`, `SignboardHeightM` | number | board size in metres |
| `SignboardReadM` | number | distance in metres from which it must be readable |
| `SignboardPosition` | text `"x,y,z"` | centre, in the consumer's global frame (B-92) |
| `SignboardNormal` | text `"x,y,z"` | unit vector pointing away from the board's face |

**B-101 · REQUIRED · signboards** - Make the main text fit the board: allow about 0.55 times the capital height of width per character plus a margin of 12 % of the board height on each side; text that cannot be fitted at a capital height of 0.05 m is an error.

**B-102 · RECOMMENDED · signboards** - Declare a reading distance your letters support: capital height in metres must be at least `pixels * readM / extensions.signboards.displayPixelsPerRadian`, with pixels from `extensions.signboards.minCapitalPixels` (primary text), and the distance within `extensions.signboards.readingDistanceMetres`.

**B-103 · RECOMMENDED · signboards** - Declare an entrance board on the wall's outer face, not the wall centre plane, and keep lamps and trees away from its face.
