<!-- chunk: g2--4-texture-sets | source: 02-interior-decorators-guide.md | title: 4. Texture sets | rules: D-40,D-41,D-42,D-43,D-44,D-45,D-46,D-47,D-48,D-49,D-50 -->
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
