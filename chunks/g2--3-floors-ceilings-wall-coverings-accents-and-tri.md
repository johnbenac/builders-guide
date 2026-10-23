<!-- chunk: g2--3-floors-ceilings-wall-coverings-accents-and-tri | source: 02-interior-decorators-guide.md | title: 3. Floors, ceilings, wall coverings, accents and trims | rules: D-10,D-11,D-12,D-13,D-20,D-21,D-30,D-31,D-32,D-33,D-34,D-35 -->
## 3. Floors, ceilings, wall coverings, accents and trims

### Floors

**D-10 · RECOMMENDED** - When you deliver a finish schedule, give every room that has a floor a floor finish: list them in the `floors` section by `Occupant`, by `RoomId` list or by pattern, plus a default. A room without a rule gets whatever the consumer defaults to.

**D-11 · RECOMMENDED** - Also write a text property `Finish` on each room (for example `light warm-grey resilient floor; pale ivory walls`), so that the intent stays with the room.

**D-12 · RECOMMENDED** - Change floor finishes at door lines, not mid-room, and keep a visible threshold between unlike finishes.

**D-13 · RECOMMENDED** - Choose low-gloss, light floors for rooms people work in: dark glossy floors read as black under many lighting set-ups.

### Ceilings

**D-20 · RECOMMENDED** - Decide ceilings through the slab or roof above: the `bottom` face of the slab above is the ceiling of the room below. To get a different ceiling finish give that slab a different colour, and describe its `bottom` slot in the schedule. A ceiling can also be an `IfcCovering` (D-31).

**D-21 · RECOMMENDED** - Keep ceiling finishes matte and light; glossy ceilings amplify lamp hot spots.

### Wall coverings

**D-30 · RECOMMENDED** - Express a wall finish through the wall element's own colour (one colour per finish and per class). It works in every consumer.

**D-31 · RECOMMENDED** - Use an `IfcCovering` (`PredefinedType` `CLADDING`, `FLOORING`, `CEILING` or `WRAPPING`) only when a finish covers part of a wall, or a surface that has no element of its own. Model it as a shell at least 10 mm thick whose back face sits exactly on the surface (touching, not overlapping), so no two faces share a plane and face the same way. Support for `IfcCovering` varies between consumers, so confirm it with the consumer first.

**D-32 · RECOMMENDED** - Do not rely on a texture pattern starting at an edge: consumers project textures differently. Design coverings that tolerate any start position, or model panels as geometry when joints must line up.

### Accents and trims

**D-33 · RECOMMENDED** - Make skirtings, cornices, door frames, handrails and accent bands separate elements with their own colour, at least 1 cm thick. Elements thinner than about 5 mm flicker against what they sit on.

**D-34 · RECOMMENDED** - Accent features (a feature wall, a coloured door, a timber panel) are a colour on the element in the same class as its neighbours, not an image inside the IFC.

### Glass

**D-35 · RECOMMENDED** - Describe glass by colour, opacity and three optional settings: base opacity, edge reflection (`fresnelAlpha`) and smudge roughness (`smudgeRough`). Keep glass light and clear: dark or green glass reads as black or milky in many viewers.
