<!-- chunk: g4--3-the-manifest | source: 04-delivery-and-acceptance-guide.md | title: 3. The manifest | rules: X-10,X-11,X-12,X-13,X-14,X-20,X-21,X-22,X-23 -->
## 3. The manifest

`manifest.json` has one entry for each of the following. Schema: `schemas/manifest.schema.json`.

| Field | Content |
|---|---|
| `format` | always `delivery-manifest/1` |
| `delivery` | `id` (lower case, dots and hyphens), `title`, `version` (SemVer), `created` (UTC date and time in the form `2026-10-22T10:00:00Z`), `supersedes` (the version it replaces, or null), `kind` (a list of `building`, `materials`, `furniture`, `mixed`) |
| `author` | `organisation`, `role` (who answers queries), `contact` (a role mailbox or handle; personal data is not needed) |
| `profile` | `name`, `version` (and optionally `sha256`) of the consumer profile you built and checked against |
| `frame` | `units` (`metres`), `axes`, `levelOffsetMetres`, `localZero` |
| `ifc` | `schema`, `entityNumberStart` |
| `files[]` | for each file: `path`, `role`, `sha256`, `bytes`, optional `version` |
| `terrain` | only with the terrain extension: `package` (`name`, `version`, `sha256` of the terrain source version used), `patch` (`path`, `sha256`), `sidecar` (`path`) |
| `counts` | numbers the checker found (levels, rooms, triangles ...) |
| `provenance[]` | for each asset group: `asset`, `type`, `source`, `author`, `licence`, `notes` |
| `licence` | `statement` that covers everything not listed in `provenance` |
| `checks` | `tool`, `toolVersion`, `report` (path in the package), `result` |

**X-10 · REQUIRED** - Put a `manifest.json` at the top of the package that matches the schema.

**X-11 · REQUIRED** - Record the SHA-256 hash (64 lower-case hexadecimal characters) and size in bytes of every file, and include a `SHA256SUMS.txt` in the plain two-column form (`hash`, two blanks, `path`). Hashes prove that what the receiving party holds is what you sent.

**X-12 · REQUIRED** - List every file in the package, and only those, in the manifest. (The manifest and the checksum file themselves are the exceptions.)

**X-13 · RECOMMENDED** - A building delivery has exactly one master IFC file (guide 1, B-03); other files are alternates.

**X-14 · REQUIRED** - Keep the whole package within the profile's cap, `package.maxPackageMegabytes`, when it sets one. Upload systems and mail gateways refuse larger packages.

**X-20 · REQUIRED** - Give every IFC file, texture set and library item a `provenance` entry (what it is, where it came from: `original`, `procedural` with the script and seed, or a named source; who made it; the licence that applies) when the profile requires provenance (`package.requireProvenance`, default true).

**X-21 · REQUIRED** - State a licence for every asset and a `licence.statement` for the package when the profile requires it (`package.requireLicence`, default true). A package whose licence terms are missing, or do not allow the receiving party to use, copy and adapt the work for the purpose of the assignment, cannot be accepted.

**X-23 · REQUIRED · terrain** - When the delivery has terrain, list the patch and its sidecar under `terrain/` with their roles, give each a provenance entry, and record the source package name, version and hash and the patch hash in the manifest `terrain` section, equal to what the sidecar states. The terrain source can change between versions (shorelines in particular), so the delivery must say exactly which version its heights came from.

**X-22 · RECOMMENDED** - Deliver only content you are free to hand over. Do not include material that is restricted, reproduced from another party's work without permission, or that carries identifying marks of a third party. If part of your work is restricted, say so in `notes/open-points.md` and leave it out.

### Machine-readable summaries

Two optional files make a delivery readable without opening the model or the schedule. Both have JSON Schemas, and `check_all.py` validates them when present (a problem is a RECOMMENDED finding, rule X-41).

| File | Schema | Content |
|---|---|---|
| `tables/building.json` | `schemas/building-metadata.schema.json` | building id and name, frame, the master file, levels with elevations and room counts, occupants, room-id prefix |
| `finishes/library.json` | `schemas/material-library.schema.json` | the texture sets (name, version, path) and the finish schedule of a material delivery |
