<!-- chunk: g2--1-how-consumers-decide-what-a-surface-looks-like | source: 02-interior-decorators-guide.md | title: 1. How consumers decide what a surface looks like | rules: - -->
## 1. How consumers decide what a surface looks like

Consumers differ here, which is why this guide is built around a portable method.

1. **IFC carries a colour and an opacity per surface style.** `IfcSurfaceStyle` with a rendering colour and a transparency is
   read by every common reader. Texture images, texture coordinates and physically based settings are read by some and ignored by
   many, so a file that relies on them looks different (or flat) in other tools.
2. **A finish schedule says what each style means.** You deliver a small JSON file that maps every (element class, colour,
   opacity) key used in the IFC to a finish: which texture set, how large one tile is, how strongly to tint it. A consumer that
   has its own materials can follow the schedule; one that does not still shows your colours.
3. **Texture sets are delivered separately,** as folders of images with a description file, so that any consumer can load them
   with its own mapping (projection, UVs, atlases).
4. **Floors, ceilings and walls use faces.** A finish can describe up to three face slots: `top` (faces pointing up, the walking
   surface), `side` (edges) and `bottom` (faces pointing down, which is the ceiling of the room below); most classes use `all`.
5. **Only emissive parts glow.** In consumers that turn fixtures into lights, the glow comes from the fixture part the profile
   names (guide 1, section 11), not from a colour.

What you control is: the class of each element, the colour and opacity you give it, the finish schedule, and the texture sets.
