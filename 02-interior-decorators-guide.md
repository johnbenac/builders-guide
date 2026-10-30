<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Guide 2: Interior Decorator's Guide

For interior decorators, material authors and texture artists who define finishes, wall coverings, floor and ceiling
treatments, accents and trims, and who deliver a reusable material library.

Rule levels and the profile mechanism are explained in the [README](README.md); profile parameters appear in `backticks`
(full list: [07-profile-parameters.md](07-profile-parameters.md)). Read sections 1 to 4 of guide 1 first: finishes attach to
the rooms and element classes defined there.

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

## 2. Colour rules

**D-01 · REQUIRED** - Give each distinct finish its own colour within an element class. The schedule keys finishes by (class, colour, opacity); two finishes with the same key are one finish. Colours that differ by less than 1/255 in every channel are the same colour.

**D-02 · REQUIRED** - Give the same finish the same colour and opacity on every element that uses it. A small drift (from re-rounding in another tool) creates a new key that has no schedule entry.

**D-03 · REQUIRED** - When you deliver a finish schedule, include an entry for every (class, colour, opacity) combination that appears in your IFC files. The checker lists them (`finishKeys`).

**D-04 · RECOMMENDED** - Use opacity below 1 only for glass and other see-through things (about 0.4 to 0.6 for glazing). Consumers treat anything with an opacity below 1 as see-through. A walkable glass floor is a slab with a glass colour and opacity.

**D-05 · RECOMMENDED** - Keep the palette small: at most `budgets.maxDistinctColours` combinations (default 50). Every combination is one more material to map, load and draw.

**D-06 · RECOMMENDED** - Treat the IFC colour as a design tint: the schedule says how strongly it is blended into the texture (0 means the texture alone, 1 the colour fully). Pick a colour near the intended look, not a code colour such as pure red.

**D-07 · RECOMMENDED** - Avoid pure black, pure white and very dark large surfaces: they clip or disappear under typical lighting. Keep large floors and walls between about 0.25 and 0.85 in mean linear luminance unless a dark look is the point.

**D-08 · RECOMMENDED** - Choose neutral tints for fabrics; strongly coloured tints shift under lighting.

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

## 4. Texture sets

A texture set is a folder of images plus a description; it is the unit of a material library.

**D-40 · REQUIRED** - Deliver every texture set as a folder `<setName>/` containing the maps the profile lists (`textures.maps`, default `albedo.png`, `normal.png`, `orm.png`) and `set.json`.

**D-41 · REQUIRED** - Use these encodings, so that every consumer reads the maps the same way:

| Map | Content | Encoding |
|---|---|---|
| `albedo.png` | base colour | 8-bit RGB PNG, **sRGB** encoded, no alpha, no baked lighting or shadows |
| `normal.png` | surface relief | 8-bit RGB PNG, **linear** data, tangent basis, flat surface = (128, 128, 255); green channel direction as the profile states (`textures.normalConvention`: `+Y` up, or `-Y`) |
| `orm.png` | packed material data | 8-bit RGB PNG, **linear** data. **R** = ambient occlusion (255 = unoccluded), **G** = roughness (0 = mirror, 255 = fully rough), **B** = metalness |

**D-42 · RECOMMENDED** - Make the texture tile seamlessly in both directions; consumers repeat it across large surfaces, and a seam repeats with it. Check the three-by-three preview.

**D-43 · REQUIRED** - Declare the physical size of one tile in `set.json` as `tileMetres`, so that a consumer can scale it correctly.

**D-44 · RECOMMENDED** - Use square, power-of-two images, all maps the same size, one of `textures.sizesPixels` (default 512, 1024, 2048). Larger maps cost memory in every view.

**D-45 · RECOMMENDED** - Choose the tile size so the texel density is inside `textures.densityPixelsPerMetre` (default 250 to 2500 pixels per metre): for 1024 pixels that is a tile of about 0.4 m to 4 m.

**D-46 · RECOMMENDED** - Avoid fine, regular weaves and stripes with a tile under 0.5 m: they produce moire at grazing angles.

**D-47 · RECOMMENDED** - Declare `tintMode` in `set.json` (one of `textures.tintModes`): `multiply` when the albedo is a near-neutral light map meant to be tinted by the IFC colour, or `authored` when the colour in the map is final.

**D-48 · RECOMMENDED** - Keep the pattern free of one-off features (a single stain, one knot) that would repeat visibly, and do not bake low-frequency variation in; consumers can add it.

**D-49 · RECOMMENDED** - If a pattern has a direction (planks, brushed metal, grain), say which image axis it follows in `set.json` (`direction`: `u`, `v` or `none`); consumers decide how directional patterns are oriented on floors and walls.

**D-50 · RECOMMENDED** - Check your tiles in a three-by-three arrangement and at a long viewing distance: fine relief that reads as speckle should be softened.

### set.json

```json
{
  "name": "plaster_fine",
  "version": "1.0.0",
  "sizePixels": 1024,
  "tileMetres": 2.0,
  "tintMode": "multiply",
  "direction": "none",
  "normalConvention": "+Y",
  "description": "fine trowelled plaster, low sheen",
  "maps": { "albedo": "albedo.png", "normal": "normal.png", "orm": "orm.png" },
  "generator": "optional: script and seed that reproduce the set"
}
```

## 5. The finish schedule

The finish schedule tells a consumer what each colour and each room floor means. The machine-readable shape is
`schemas/finish-schedule.schema.json`; a starting file is `templates/finish-schedule.template.json`.

**D-60 · REQUIRED** - Deliver `finish-schedule.json` with these sections: `format` (`finish-schedule/1`), `delivery`, `version` (SemVer), `materials[]` (one entry per (class, colour, opacity) key: `key`, `role`, `usedBy`, `faces`), `floors[]` (ordered floor rules: `where` and `finish`), and `libraries[]` (the texture-set folders it names, with versions).

**D-61 · REQUIRED** - Name only texture sets that exist: each face entry names a set from your delivery or from a library the profile or consumer publishes. Settings are optional:

| Setting | Meaning |
|---|---|
| `set` | texture-set name |
| `tint` | `"ifc"` (the element's colour), a colour such as `"#5a5654"`, or `"none"` |
| `tintStrength` | 0 to 1: how far the tint replaces the texture's own colour |
| `tileMetres` | override the set's tile size |
| `normalScale` | strength of relief (typically 0.4 to 1.3) |
| `roughMul`, `metalMul` | multipliers on roughness and metalness |
| `macroStrength`, `macroScaleMetres` | optional low-frequency variation to hide repetition |
| `aoStrength` | strength of baked occlusion |
| `sheen`, `sheenTint` | fabric edge response |
| `offsetMetres` | shift the pattern so neighbouring materials do not repeat in step |

**D-62 · RECOMMENDED** - Mark materials that must stay as they are (emissive strips, planning markers) with `"keep": true` and a reason instead of giving them a texture.

**D-63 · RECOMMENDED** - Treat the schedule as a proposal: a consumer applies what it can. Do not depend on any single setting being honoured exactly.

### A short example

```json
{
  "format": "finish-schedule/1",
  "delivery": "example-room-1.0.0",
  "version": "1.0.0",
  "materials": [
    { "key": { "class": "IfcWall", "colour": "#d9d2c3", "opacity": 1.0 },
      "role": "room walls", "usedBy": "all rooms",
      "faces": { "all": { "set": "plaster_fine", "tint": "ifc", "tintStrength": 0.55, "normalScale": 0.6 } } },
    { "key": { "class": "IfcSlab", "colour": "#c9c4b8", "opacity": 1.0 },
      "role": "floor slab", "usedBy": "all levels",
      "faces": { "top": { "set": "concrete_polished", "tint": "ifc", "tintStrength": 0.25 },
                 "side": { "set": "board_concrete" },
                 "bottom": { "set": "ceiling_gypsum" } } }
  ],
  "floors": [
    { "id": "floor-default", "where": { "occupant": "*" }, "finish": { "set": "oak_plank_wide" } }
  ],
  "libraries": [ { "name": "plaster_fine", "version": "1.0.0" } ]
}
```

## 6. Palettes

**D-70 · RECOMMENDED** - Build the palette from a few families and give each organisation or zone a distinct tint rather than a distinct pattern.

**D-71 · RECOMMENDED** - Describe the intent in words as well as colours ("light warm-grey resilient floor; pale ivory washable walls; low gloss"), so that a consumer with its own material library can choose.

**D-72 · RECOMMENDED** - Do not use texture or colour to carry meaning that labels already carry (room names, identifiers, directions). Use finish to make places feel different, not to label them.

## 7. Delivering a reusable material library

A library is a set of texture sets plus a finish schedule, with a manifest (guide 4). It is reusable when a different building can name your sets in its own schedule. `finishes/library.json` (`schemas/material-library.schema.json`) lists the sets and the schedule.

**D-80 · REQUIRED** - Record the source and licence of every texture set and every image in it in a `SOURCES.csv` next to the library with the columns `asset,type,source,licence,notes`. State whether the set is procedural (and which script and seed make it) or derived from photographs (and whose). Include no image whose licence you cannot state.

**D-81 · REQUIRED** - Include the SHA-256 hash of every file in the manifest (guide 4).

**D-82 · RECOMMENDED** - Prefer procedural sets with the generator and its seeds included; byte-identical output lets a consumer verify and regenerate the library and keeps the delivery small.

**D-83 · RECOMMENDED** - Name sets in lower case with underscores (`limewash_mottled`) and finishes with dotted names (`wall.limewash.warm`). Give each set its own SemVer; a changed look is a new version, never an overwrite.

**D-84 · RECOMMENDED** - Include a contact sheet (a PNG with each set's albedo, normal and roughness side by side, plus the tile size) so a reviewer sees the library at a glance.

**D-85 · RECOMMENDED** - Keep the library independent of any one building: no file name, label or set name should refer to a particular project.

## 8. Defects commonly seen

| Defect | Cause | What to do |
|---|---|---|
| fabrics read pale or tinted | strongly coloured tint | neutral tint, lower sheen (D-08) |
| stone chips too bold | high chip contrast | soften relief and chip mask |
| woven wall cloth shows moire | small tile, strong relief | larger tile, lower relief (D-46) |
| carpets and floors read near black | very low albedo | lighter albedo (D-07) |
| parquet reads as staggered strips | pattern repeat scale | check the three-by-three view (D-50) |
| concrete pores read as spots | relief too sharp | soften relief (D-50) |
| glazing milky or black | dark or green glass colour | light clear glass (D-35) |
| blotchy walls | uneven lighting plus strong variation | moderate variation (D-48) |

## Exported appearance review

Review UV scale, grain direction, masonry corners, normal strength, surface-specific roughness/metallic response and clear-glass optics in the actual exported consumer artifact. An exporter or preview must not silently replace authored surfaces to make its image look correct. Inspect closeups and ordinary room views; use [guide 9](09-environment-review-and-handoff.md) to record evidence and limitations.
