<!-- chunk: g5--3-step-by-step-3-7-the-luminaire-optional-extens | source: 05-worked-example.md | title: 3. Step by step: 3.7 The luminaire (optional extension; B-90 to B-93) | rules: - -->
### 3.7 The luminaire (optional extension; B-90 to B-93)

One assembly with a housing part and an emissive part whose name ends in ` lens`. The assembly carries the declaration properties.
The emissive part's centre is at local (2.6, 2.1, 2.89). Under a profile with a frame offset, the declared position is in the
consumer's global frame, so the height gets the offset added once:

| Property | Value |
|---|---|
| `LightPositionLocal` | `2.6,2.1,2.89` (optional, for checking) |
| `LightPosition` | `2.6,2.1,14.89` (2.89 + 12.0) |
| `LightAim` | `0,0,-1` (unit length) |
| `LightType`, `LightEnergy`, `LightRangeM`, `LightSpotDeg` | `spot`, 6, 8, 78 |
| `LightColor` | `1,0.87,0.7` (warm) |
| `LightFadeBeginM`, `LightFadeLengthM` | 40, 20 |
| `LuminaireTarget` | `EX-001` |

With the luminaires extension enabled, the checker confirms that the emissive part's centre plus the offset is within the profile's
tolerance of `LightPosition`. Under the default profile (extension off) the fixture is simply a light fixture.
