<!-- chunk: g1--13-geometry-hygiene | source: 01-builders-and-architects-guide.md | title: 13. Geometry hygiene | rules: B-110,B-111,B-112,B-113,B-114,B-115,B-116 -->
## 13. Geometry hygiene

**B-110 · REQUIRED** - Keep all geometry inside the profile's build volume (`buildVolume`) and outside its keep-out regions (`keepOut`), when it gives them; check every vertex, not only footprints. The terrain element of the terrain extension (section 16) is context supplied by the consumer's terrain source and is not checked against the build volume.

**B-111 · RECOMMENDED** - Make solids closed and consistently oriented: no missing faces, no inside-out solids, no zero-area or duplicate faces.

**B-112 · RECOMMENDED** - Avoid coplanar overlapping faces (two walls sharing a face, a covering lying exactly on a wall, a slab exactly on a floor). Offset thin layers or merge them.

**B-113 · RECOMMENDED** - Use mapped items (`IfcMappedItem` with `IfcRepresentationMap`) for repeated parts. They keep files small; most consumers expand them to ordinary triangles, so they save file size, not drawing cost.

**B-114 · RECOMMENDED** - Do not model what cannot be seen or used: hidden interiors, bolts, hinge detail, text as geometry, curves with more than `geometry.maxCurveSegmentsPerCircle` segments per full circle.

**B-115 · RECOMMENDED** - Do not model terrain, soil or relief in IFC unless the profile says how. Trees and planting may be `IfcGeographicElement` markers; consumers differ on whether they are solid. The terrain extension (section 16) is how a profile says how: with it, the only terrain in the file is the derived patch it describes.

**B-116 · RECOMMENDED** - Do not model a thin layer at a height where the consumer adds its own surface layer (floor finishes laid on the room floor); two layers at one height flicker.
