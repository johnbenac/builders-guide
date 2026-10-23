<!-- chunk: g5--3-step-by-step-3-8-colours-and-the-finish-schedu | source: 05-worked-example.md | title: 3. Step by step: 3.8 Colours and the finish schedule (guide 2) | rules: - -->
### 3.8 Colours and the finish schedule (guide 2)

Each (class, colour, opacity) combination needs a finish. The checker finds nine:

| Class | Colour | Opacity | Used for |
|---|---|---|---|
| `IfcWall` | `#d9d2c3` | 1.0 | all four walls (one finish) |
| `IfcSlab` | `#c9c4b8` | 1.0 | floor slab |
| `IfcSlab` | `#e8e4da` | 1.0 | roof slab, whose underside is the ceiling |
| `IfcDoor` | `#977353` | 1.0 | door leaf |
| `IfcWindow` | `#91c8d0` | 0.45 | glass |
| `IfcFurnishingElement` | `#ccbba0` | 1.0 | the table |
| `IfcCovering` | `#8c6f4e` | 1.0 | the wall covering |
| `IfcLightFixture` | `#3d4348` | 1.0 | luminaire housing |
| `IfcLightFixture` | `#fff0cf` | 1.0 | luminaire emissive part |

`finishes/finish-schedule.json` has one entry for each, and a floor rule for `Example Occupant`. The slab entries use all three face
slots: `top` for the floor, `bottom` for the ceiling, `side` for the edge.
