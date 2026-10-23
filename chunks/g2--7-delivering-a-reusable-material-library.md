<!-- chunk: g2--7-delivering-a-reusable-material-library | source: 02-interior-decorators-guide.md | title: 7. Delivering a reusable material library | rules: D-80,D-81,D-82,D-83,D-84,D-85 -->
## 7. Delivering a reusable material library

A library is a set of texture sets plus a finish schedule, with a manifest (guide 4). It is reusable when a different building can name your sets in its own schedule. `finishes/library.json` (`schemas/material-library.schema.json`) lists the sets and the schedule.

**D-80 · REQUIRED** - Record the source and licence of every texture set and every image in it in a `SOURCES.csv` next to the library with the columns `asset,type,source,licence,notes`. State whether the set is procedural (and which script and seed make it) or derived from photographs (and whose). Include no image whose licence you cannot state.

**D-81 · REQUIRED** - Include the SHA-256 hash of every file in the manifest (guide 4).

**D-82 · RECOMMENDED** - Prefer procedural sets with the generator and its seeds included; byte-identical output lets a consumer verify and regenerate the library and keeps the delivery small.

**D-83 · RECOMMENDED** - Name sets in lower case with underscores (`limewash_mottled`) and finishes with dotted names (`wall.limewash.warm`). Give each set its own SemVer; a changed look is a new version, never an overwrite.

**D-84 · RECOMMENDED** - Include a contact sheet (a PNG with each set's albedo, normal and roughness side by side, plus the tile size) so a reviewer sees the library at a glance.

**D-85 · RECOMMENDED** - Keep the library independent of any one building: no file name, label or set name should refer to a particular project.
