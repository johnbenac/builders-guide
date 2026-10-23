<!-- chunk: g2--5-the-finish-schedule | source: 02-interior-decorators-guide.md | title: 5. The finish schedule | rules: D-60,D-61,D-62,D-63 -->
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
