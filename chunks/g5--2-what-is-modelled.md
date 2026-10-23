<!-- chunk: g5--2-what-is-modelled | source: 05-worked-example.md | title: 2. What is modelled | rules: - -->
## 2. What is modelled

```
  y
  4.2 +--------------[ window 1.5 x 1.2, sill 0.9 ]----------+
      |                                                       |
      |  covering          (table 1.6 x 0.8,                  |
      |  3.0 x 2.4          light above it)                   |
      |                                                       |
  0.0 +---[ door 1.2 x 2.3 ]----------------------------------+
      0.0                                                    5.2  x
```

| Element | Class | Size and position (file-local metres) |
|---|---|---|
| floor slab | `IfcSlab` `FLOOR` | 5.2 by 4.2 by 0.3, top face at z = 0 |
| roof slab | `IfcSlab` `ROOF` | 5.2 by 4.2 by 0.3, underside at z = 3.0 (the ceiling) |
| south, north, west, east walls | `IfcWall` | 0.2 thick, 3.0 high |
| door opening and door | `IfcOpeningElement`, `IfcDoor` | south wall, x from 0.8 to 2.0, 2.3 high |
| window opening and window | `IfcOpeningElement`, `IfcWindow` | north wall, x from 2.0 to 3.5, from 0.9 to 2.1 high, opacity 0.45 |
| room | `IfcSpace` | inside faces: 4.8 by 3.8 by 3.0, floor at z = 0 |
| table | `IfcFurnishingElement`, mapped item | 1.6 by 0.8 by 0.74, pivot at the footprint centre, placed at (2.6, 2.1, 0) |
| wall covering | `IfcCovering` `CLADDING` | on the west wall's inside face: 10 mm thick, 3.0 m wide, from 0.1 to 2.5 high |
| luminaire | `IfcElementAssembly` with two `IfcLightFixture` parts | centred over the table, emissive part centre at (2.6, 2.1, 2.89) |
