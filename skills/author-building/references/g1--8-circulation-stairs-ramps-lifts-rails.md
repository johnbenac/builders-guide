<!-- chunk: g1--8-circulation-stairs-ramps-lifts-rails | source: 01-builders-and-architects-guide.md | title: 8. Circulation, stairs, ramps, lifts, rails | rules: B-60,B-61,B-62,B-63,B-64,B-65,B-66,B-67 -->
## 8. Circulation, stairs, ramps, lifts, rails

**B-60 · REQUIRED** - Model each stair flight as an `IfcStairFlight` (a parent `IfcStair` without geometry is fine). Consumers recognise stairs, and simulators build their walking surface, from the flight.

**B-61 · RECOMMENDED** - Keep risers at or below `geometry.stairRiserLimitMetres`, with a landing and head-room; avoid winding and spiral stairs unless you have checked the consumer reads them.

**B-62 · RECOMMENDED** - Give every multi-level building at least one real stair. Lifts drawn in IFC are often static solids; a stair is the one way between levels that every consumer understands.

**B-63 · RECOMMENDED** - Draw lifts as `IfcTransportElement` with `PredefinedType` `ELEVATOR`, with properties such as `Service`, `StopsMetres` and `ShaftWidthMetres`.

**B-64 · RECOMMENDED** - Keep every walked slope at or below `geometry.rampMaxSlope` (rise over run) except stairs, and give ramps a clear width at least as wide as a doorway. Model ramps as `IfcRamp` with `IfcRampFlight`, or as a sloped `IfcSlab`.

**B-65 · RECOMMENDED · walkability** - Do not leave low obstacles up to `extensions.walkability.stepHeightMetres` high (floor boxes, square-edged wedges) that a walker steps over unseen; ramp them or make them visible steps.

**B-66 · RECOMMENDED** - Model rails (`IfcRailing`) with cheap geometry: simple posts and one rail section. Rails with dense tessellation are a common cause of heavy files.

**B-67 · RECOMMENDED · walkability** - Know which classes the consumer treats as not solid (`extensions.walkability.nonSolidClasses`) and model walk-through areas with those classes or with reservation volumes (B-80); everything else may block movement.

### Clearance and size summary

| Item | Value | Where it comes from |
|---|---|---|
| doorway clear height | at least `geometry.doorMinClearHeightMetres` | B-42 |
| doorway probe heights | `geometry.doorwayProbeHeightsMetres` | B-42 |
| doorway clear width | at least `geometry.doorMinClearWidthMetres` | B-43 |
| stair riser | at most `geometry.stairRiserLimitMetres` | B-61 |
| walked ramp slope | at most `geometry.rampMaxSlope` | B-64 |
| free floor around fixed objects | `extensions.walkability.standingClearanceMetres` | B-33 |
| free floor circle in a room | `extensions.walkability.freeCircleMetres` | B-34 |
