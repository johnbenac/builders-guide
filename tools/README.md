<!-- SPDX-License-Identifier: Apache-2.0 -->
# Tools

Scripts that let you check your own work the way the receiving party will. All are plain Python 3, print what they
checked, and exit with status 1 when a REQUIRED rule fails.

Install once: `pip install -r tools/requirements.txt` (IFC reading, arrays, images, JSON schema checks, footprint geometry, scipy for `walkcheck.py` and the terrain tools). `preview.py` needs
`requirements-preview.txt` (matplotlib); each file includes the core list. The set is tested with ifcopenshell 0.9.0.post1, numpy 2.5.3, pillow 12.3.0, jsonschema 4.26.0, shapely 2.2.0, scipy 1.18.1 and
matplotlib 3.11.2 and, for the optional Khronos validator, Node.js 20 with gltf-validator 2.0.0-dev.3.10; the file lists give the lowest versions the code is written for and a loose upper bound (the next major version, or for ifcopenshell the next minor one). Building the hand-over files needs `requirements-dist.txt` (pikepdf), pandoc and a Chromium-based browser.

| Script | Use |
|---|---|
| `check_all.py` | one entry point: runs every check that applies to a master file, a finishes folder, an items folder or a package, and prints one report (`--json`, `--out`) |
| `check_ifc.py` | acceptance checks for a master IFC file (guide 4, section 5). Options: `--profile`, `--finish-schedule`, `--level-offset`, `--known-room-ids`, `--report`, `--json` |
| `check_texture_set.py` | checks for one texture set folder (guide 2, section 4); `--preview` writes a three-by-three wrap picture |
| `check_item.py` | checks for one library item folder (guide 3) |
| `build_package.py` | `init` writes the manifest and checksum file (`--manifest-name delivery.json` for a submitted delivery); `verify` runs the package checks (guide 4) |
| `check_submission.py` | form checks of a submitted delivery folder `deliveries/<slug>/`: layout, licence and attestation, file types, counts and sizes, safe paths, links, file contents (X-70 to X-78); `check_all.py` runs it on any folder that has a `delivery.json` |
| `export_glb.py` | IFC to GLB: the whole model as a named scene graph, and one GLB per item, covering, fixture, hardware piece, door, window and texture set (units metres, Y up, PBR materials, deterministic bytes); prints the SHA-256 of each (guide 4, section 8.1). Options for the whole-model GLB: `--volumes exclude` (zones and reservation volumes left out and listed), `--pivots placement` (a pivot and a placement per product, shared meshes, `placements.json`), `--pivot-file`, `--indexed`, `--coplanar union` |
| `validate_glb.py` | structure and convention checks of GLB files (indices, accessors, images, materials, scene graph, nothing unused, no URI, units and axes, normals and tangents, budgets, scene-graph names, bounding boxes against the IFC file) plus the Khronos glTF Validator when installed (`npm ci --prefix tools/khronos`); report in `check-report/1` (X-80) |
| `coplanar.py` | coincident faces: lists the pairs of nodes of a GLB whose same-facing faces lie in one plane and overlap (z-fighting), and merges such overlaps inside one product (`export_glb.py --coplanar union`) |
| `walkcheck.py` | a 3D voxel walk through a whole-model GLB at one or more body radii: which rooms can be reached from a start point, which waypoints are connected (`schemas/walk-report.schema.json`); `--require RADIUS` gives an exit code |
| `check_set.py` | checks a staged copy of the set: version agreement (CHANGELOG, rules.json, MANIFEST.json, every tool), every file of MANIFEST.sha256 present and unedited, required files present, `--expect X.Y.Z` |
| `test_glb_options.py` | tests the optional export and check features: volume exclusion, pivots and instancing, node-transform bounds, coincident faces, the walk check, `check_set.py` |
| `render.py` | headless, deterministic software renders of GLB files: a plan per level, interior views per room kind, exterior views and a turntable contact sheet per component; no GPU, display or browser |
| `build_proofs.py` | runs export, validation and render for a delivery and writes `proofs/` with its `manifest.json` (`schemas/proofs.schema.json`) |
| `check_proofs.py` | checks the proofs of a delivery (X-79 to X-86); `--reproduce` rebuilds the GLB files and re-renders every picture and compares them within the profile's tolerance |
| `glbkit.py`, `proofkit.py` | shared helpers: IFC products to triangles and GLB bytes (also used by `ingest.py`), GLB reading, PNG and JPEG metadata, picture comparison |
| `ingest.py` | turns a merged delivery into component assets (GLB), content-addressed blobs, a neutral catalogue and a handoff manifest; `--dry-run`, limits, never uploads (`08-submissions-and-ingest.md`) |
| `make_sample_delivery.py`, `test_submission.py`, `test_proofs.py` | build the sample delivery `deliveries/example-room/` (with its proofs); test the submission checks (28 broken deliveries) and ingest (catalogue, hashes, deduplication, determinism, refusals); test the proof tools (about thirty broken GLB files and proof sets, reproduction, ingest comparison) |
| `khronos/` | `package.json` and `package-lock.json` pinning the Khronos glTF Validator (npm `gltf-validator`, Apache-2.0, not vendored) and `validate.mjs`, the small wrapper `validate_glb.py` calls |
| `ci/` | `run_checks.sh` runs the delivery checks the pull-request workflow runs, without any workflow system; `check-delivery.yml` is the workflow itself (`requirements-ci.txt` pins the libraries it uses) |
| `map_properties.py` | consumer intake: renames declaration properties between the neutral names and a consumer's names, using a mapping file the receiving party keeps outside this set (`--reverse` undoes it). `test_map_properties.py` tests it |
| `make_sample.py`, `make_sample_item.py`, `make_sample_texture_set.py` | generate the pieces of the worked example (guide 5) |
| `site_request.py` | terrain extension: writes the request a building sends its terrain source (footprint polygon, finished floor elevation, grading rule, clearing margin, smallest patch) from a master file |
| `terrain_import.py` | terrain extension: reads a height patch (GeoTIFF) with its sidecar and a site request, reduces it to a triangulated network within an error bound and adds the derived terrain element, georeference and site data to a copy of the master file |
| `make_sample_terrain.py` | writes a trivial synthetic plane or slope patch and sidecar for tests and examples; real terrain comes from the terrain source |
| `terrain_lib.py`, `test_terrain.py` | shared terrain helpers (GeoTIFF reader, error-bounded reduction, height lookup) and their tests |
| `ifc_author.py` | authoring kit: levels, slabs, walls with openings, stairs with correctly sized wells, gable roofs, battered walls, rooms (internal and open-air) with their declaration properties, deterministic output; see `make_fixtures.py` |
| `make_fixtures.py`, `test_fixtures.py` | three worked buildings built with the kit (cantilevered trays, a rotated stepped hillside block, a courtyard with battered walls) and their tests |
| `preview.py` | draws one plan per level and an isometric view of a master file (needs matplotlib) |
| `run_example.py` | builds, checks and packages the whole worked example in one go |
| `selftest.py` | builds the worked example, breaks it eleven ways, tests the property mapper, the generated files and the agent harness and confirms the checker names the right rule each time |
| `rules_index.py` | regenerates `06-rules-index.md` and cross-checks every rule id used in the guides and scripts |
| `build_dist.py` | builds the combined HTML and PDF and the zip with its checksums; renders from a neutral folder and removes local-file links from the PDF |
| `leakscan.py` | finds local-file addresses and absolute local paths in the set and in the hand-over files (zip members, PDF streams and links); run by `test_sync.py` |
| `gen_all.py` | writes or checks every generated file: `rules.json`, `chunks/`, `llms.txt`, `llms-full.txt`, `skills/*/references/`, `06-rules-index.md`, `MANIFEST.json` |
| `rules_meta.json` | machine fields of the rules (rationale, fix hint, examples, related, which tool checks them); with the guides it is the source of `rules.json` |
| `test_sync.py` | fails if the guides and the generated files differ, or a skill, link or hash is wrong, or a file holds a local path |
| `agent_harness.py` | simulates a fresh agent: builds a building, a material library, an item and a package from the set alone, repairs one finding, then breaks each rule category and checks the findings |
| `report.py` | shared report format |

Report format (`schemas/check-report.schema.json`): `schema`, `tool`, `toolVersion`, `target`, `result` (`pass`, `fail`, `error`),
`exitCode`, `summary`, `findings`. Every finding has a stable `id`, `rule`, `level`, `status` (`pass`, `info`, `warn`, `fail`),
`severity`, `location` (`file`, `element` = the product's `GlobalId`), `message` and, on `warn` and `fail`, `fix_hint`.
Exit codes: 0 no REQUIRED failure, 1 at least one, 2 wrong command line, 3 unreadable input.
