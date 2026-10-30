<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Changelog

Format: newest first. See `VERSIONING.md` for what each kind of change means.

## 2.5.0

Review follow-up: retain all contact witnesses, test intermediate articulation,
inspect functional cavities and explicit surface intent, verify actual lightmap
sampling support, and record asynchronous ownership and reproduction limits.

Added an application-neutral environment-review and asynchronous-handoff procedure and optional machine-readable work record. Connects existing construction, finish and acceptance guidance to complete-room coverage, source/export parity, consumer rendering, door-pose collision, artifact invalidation and remote continuation. Clarifies that technical proof checks do not establish visual or device acceptance. No rule levels, profile limits, package formats or default checker outcomes change.

## 2.4.0

Optional GLB export features and checks that consumers who move, open and walk through the model need, and a check of staged copies. MINOR under
`VERSIONING.md`: every new behaviour of an existing tool is behind an option or a profile parameter whose default reproduces 2.3.0 (the default GLB bytes
of the sample delivery and of the three generated fixtures are unchanged), new tools, new profile parameters with defaults that keep existing deliveries
passing (default profile 1.3.0 to 1.4.0), and new automated checks that can only warn (`RECOMMENDED`, estimates). The two places where a REQUIRED check is
stricter are named under **Compatibility**.

**Added**

* **Zones and reservation volumes in the whole-model GLB** (`X-80`, `X-81`): `export_glb.py --volumes exclude` (profile `proofs.glbVolumes`, default
  `mesh`) leaves `IfcSpatialZone` and `PROVISIONFORSPACE` proxies out, also when they are parts of an assembly, and lists them in `extras.excluded`;
  `validate_glb.py --ifc` accepts a missing node only for a product on that list that is one of those two kinds, refuses a listed product that has a
  node, and reports the number of all products without a node.
* **Per-product pivots, instancing, indexed meshes, placements table** (`X-80`, `X-81`): `export_glb.py --pivots world|placement|footprint` (profile
  `proofs.glbPivots`, default `world`), `--pivot-file` (hinge points; every entry must match a node that takes a pivot, and the applied ones are recorded
  in `extras.pivotOverrides`), `--indexed` / `--no-indexed` (`proofs.glbIndexed`), and `model.placements.json` (`schemas/placements.schema.json`, format
  `placements/1`, one row per node, terrain included). Meshes that nodes share are named `shape:<hash>`. Component GLB files and swatches are unchanged,
  so component identifiers are unchanged.
* **`GLB-IDENT`** (`X-80`, `RECOMMENDED`): the GlobalId in a node name equals `extras.globalId`, and one GlobalId is on one node.
* **Coincident faces:** `tools/coplanar.py` (pairs of nodes with same-facing coplanar overlapping faces, and the union of such overlaps inside one product;
  one definition of "the same plane" for both, a stated triangle and time budget), `GLB-COPLANAR` (`X-80`, `RECOMMENDED`, an estimate; profile
  `budgets.coincidentFaceMinAreaM2`, default 0.005; "could not run" is a finding, never a clean result), `export_glb.py --coplanar union`
  (`proofs.glbCoplanar`, default `off`).
* **`tools/walkcheck.py`** (`schemas/walk-report.schema.json`, format `walk-report/1`): a 3D voxel walk through a whole-model GLB at one or more body radii.
  The step height defaults to the profile's `geometry.stairRiserLimitMetres` (`--step`, `--riser`, `--profile`), the grid covers the whole model, and the
  memory it needs is checked against a stated budget (`--max-memory-mb`) before anything is allocated.
* **`tools/check_set.py`:** a staged copy of the set agrees with itself on its version, both manifests list the same files with the same hashes, nothing
  escapes the folder, the zip and checksum files in `dist/` match, and it holds what it must. `test_sync.py` runs it on the repository and `build_dist.py`
  on the finished hand-over files.
* **`tools/test_glb_options.py`** and **`tools/test_glb_negative.py`** test all of the above, the second one what must be refused.
* **`.github/workflows/check-set.yml`**: `gen_all.py --check`, `test_sync.py` and `selftest.py` run on pull requests and pushes to `main` that change the
  tools, profiles, schemas, rules, guides or skills.

**Changed**

* `validate_glb.py` takes the transforms of the nodes into account for `GLB-BOUNDS`, `GLB-EXTENT` and the bounds it reports (a GLB whose nodes carry their own
  pivots no longer reports wrong bounds); for a GLB whose vertices are baked into world space the result is the same as before.
* `tools/requirements.txt` and `tools/requirements-ci.txt` declare scipy (used by `walkcheck.py`); the shapely floor is 2.1 (the constrained Delaunay
  triangulation of the coplanar union, as the documentation already said).
* The default profile is 1.4.0: `budgets.coincidentFaceMinAreaM2` and `proofs.glbVolumes`, `glbPivots`, `glbIndexed`, `glbCoplanar`, all with defaults
  that reproduce 2.3.0.

**Compatibility**

* A GLB with node transforms (none is written by 2.3.0: its vertices are baked into world space) whose `extras.bounds` were computed from the raw vertices
  passed `GLB-BOUNDS` and `GLB-EXTENT` (REQUIRED) before and can fail now, because the bounds are those of the scene. `GLB-NODE` (REQUIRED) now also refuses
  a malformed transform (wrong length, not finite) and a `matrix` that mirrors, collapses an axis or projects, which the `scale` rule already refused for
  `scale`. `extras.excluded`, when present, is validated (`GLB-EXTRAS`, REQUIRED). These cannot affect a GLB written by `export_glb.py` 2.3.0 or by
  `build_proofs.py`, so no delivery of the set passes or fails differently; a hand-made GLB with transforms could.
* `walkcheck.py`, `coplanar.py` and `check_set.py` are new; nothing depends on them.

## 2.3.0

Every submitted delivery now carries standalone, reproducible visual proofs: GLB exports of the model and of every component, a GLB validation report
and a standard set of rendered pictures, tied together by a proof manifest. MINOR under `VERSIONING.md`: new tools, new rules that apply only to
deliveries submitted as pull requests (`applies_to` `submission`, so they cannot change how any other package passes), a new profile group and a
relaxed default limit (`submission.maxFiles` 200 to 600, because proofs add files); no building, item or finish passes or fails differently.

**Added**

* **New rules `X-79` to `X-86`** (REQUIRED, `submission` only; guide 4, section 8.1): proof manifest and nothing else in `proofs/` (`X-79`), valid GLB files in
  metres with Y up (`X-80`, `tools/validate_glb.py`), a GLB of the whole model and of every item, covering, fixture, hardware piece, door, window and texture
  set, made from the delivered files, with a passing validation report that names each by hash (`X-81`), renders that cover every level, every room kind,
  the outside and every component (`X-82`), every picture traced by hash to a delivered GLB (`X-83`), pixel and size limits (`X-84`), no personal data or
  paths in image or GLB metadata (`X-85`), reproducibility: a rebuild gives the same GLB bytes and a re-render the same pictures within a stated
  tolerance, with a clear skip (not a pass) when the toolchain is missing (`X-86`). `X-79`, `X-81` to `X-86` are checked by `tools/check_proofs.py`
  (run by `check_all.py` on a delivery; `--reproduce` adds `X-86`), `X-80` by `tools/validate_glb.py`.
* **Tools:** `export_glb.py` (IFC to GLB, whole model as a named scene graph and one GLB per component, PBR materials, deterministic bytes, the same
  component GLB files `ingest.py` stores), `validate_glb.py` (pure-Python structure and convention validator, bounding boxes against the IFC file, optional
  Khronos glTF Validator, pinned in `tools/khronos/package-lock.json`, not vendored), `render.py` (headless numpy software rasteriser: plans, interior
  views, exterior views, turntable contact sheets; no GPU, display or browser), `build_proofs.py`, `check_proofs.py`, shared `glbkit.py` and `proofkit.py`,
  and `test_proofs.py`.
* **`schemas/proofs.schema.json`** (format `proofs/1`): per delivery `proofs/manifest.json` with each GLB (SHA-256, size, source IFC hash), the validation
  report hash, each render (path, SHA-256, pixel size, camera, light, GLB hash, tool and version) and a coverage statement.
* **Profile `proofs` group** (default profile 1.3.0): `maxGlbNodes`, `maxExtentMetres`, `interiorViewsPerRoom`, `maxRoomsPerKind`, `exteriorViews`,
  `turntableFrames`, `minRenderWidth`, `maxRenderPixels`, `maxRenderBytes`, `maxProofBytes`, `renderTolerance`.
* **Ingest** compares the contributor's proofs with a fresh export from the delivered files and reports any mismatch (the ingest result stays
  authoritative, nothing is refused for it), links each component to its contact sheet (`proof-render` file) and lists the renders and GLB files in the
  delivery record (`catalogue-delivery/1` gains an optional `proofs` object).
* **CI:** `.github/workflows/check-delivery.yml` installs the pinned Khronos validator (public package, no secret, install scripts off), rebuilds the
  proofs on the runner (`check_proofs.py --reproduce`) and runs `validate_glb.py`; still the plain `pull_request` event with a read-only token and pinned
  actions, plus `workflow_dispatch` for a maintainer. `tools/ci/run_checks.py` runs the same steps.
* **Manifest roles** `proof-manifest`, `proof-glb`, `proof-render`, `proof-report` in `schemas/manifest.schema.json`.

**Changed**

* `tools/ingest.py` uses the shared `tools/glbkit.py` for geometry and GLB code; the component GLB bytes, and so the component identifiers, are unchanged
  from 2.2.0.
* `tools/preview.py` writes PNG files without the plotting library's version text.
* `deliveries/example-room` carries real proofs (7 GLB files, 15 renders).
* `submission.maxFiles` default 200 to 600 (relaxed limit).

## 2.2.0

Outside contributors can offer deliveries to the same repository as pull requests from forks, with automatic checks, and a merged delivery can be
turned into component assets and a neutral catalogue. MINOR under `VERSIONING.md`: new tools, new rules that apply only to submitted deliveries,
new profile parameters with defaults; no existing package or building passes or fails differently.

**Added**

* **Submissions.** `deliveries/<slug>/` holds a delivery (a package whose manifest is `delivery.json` with a `submission` object,
  `schemas/submission.schema.json`); `deliveries/example-room/` is a small sample built from the worked example. Deliveries are left out of the
  set's file list, `MANIFEST.json`, the zip and the generated documents (`tools/fileset.py`). Contributors fork, build in a branch of the fork and open
  a pull request against `main`; `.github/pull_request_template.md` carries the licence and sign-off checklist (CC BY 4.0 unless CC0 is stated;
  ownership and no restricted content attested).
* **New rules `X-70` to `X-78`** (`applies_to` `submission`, checked by `tools/check_submission.py`, run by `check_all.py` on any folder with a
  `delivery.json`): layout and submission block, licence, allowed file types (no programs, scripts, archives, executable modes), counts and sizes,
  safe paths, no links, attestation, file contents match their type, preview picture (`X-78` RECOMMENDED; the rest REQUIRED for submitted deliveries only).
* **Profile `submission` group** (default profile 1.2.0): `maxFiles`, `maxFileBytes`, `maxDeliveryBytes`, `maxPathLength`, `allowedExtensions`,
  `allowedLicences`, `maxImagePixels`, `ingestMaxComponents`, `ingestMaxSeconds`.
* **Checks in CI.** `.github/workflows/check-delivery.yml` (pull requests touching `deliveries/**`; read-only token, no secrets, no
  `pull_request_target`; JSON reports as an artifact) and the workflow-free `tools/ci/run_checks.sh`; `tools/requirements-ci.txt` pins the libraries.
* **Ingest** `tools/ingest.py`: runs on a merged commit, re-runs the checks, splits a delivery into components (items, furniture, coverings, fixtures,
  luminaire assemblies, hardware, doors, windows, material sets), exports verified GLB geometry, stores blobs by SHA-256 (deduplicated across
  deliveries), writes `catalogue/index.json`, per-delivery records and a handoff manifest (`schemas/catalogue.schema.json`). Deterministic, limited in
  time and memory, `--dry-run`, never uploads.
* **Documents:** `08-submissions-and-ingest.md`, guide 4 section 8, the skill `skills/submit-delivery`, `deliveries/README.md`.
* **Tests:** `tools/test_submission.py`.

**Changed**

* `build_package.py` reads `delivery.json` when a package has no `manifest.json` (`init --manifest-name`).
* `schemas/rules.schema.json` allows `applies_to` `submission`.

## 2.1.0

An authoring kit, automated checks for rules that were review-only, rules for sites and forms the one-room example did not cover, and an
optional terrain extension. MINOR under `VERSIONING.md`: no default-profile delivery changes from pass to fail (every new automated
check is RECOMMENDED and only warns; the REQUIRED rules are inside the new extension, which is off by default).

**Added**

* **Authoring kit** `tools/ifc_author.py`: levels, slabs, walls with openings, stairs with wells sized for head-room, gable roofs, battered
  walls, internal and open-air rooms, footings, deterministic output. It fails loudly (unknown opening kind, repeated key, opening outside
  its wall, nonsense stair) and takes its numbers (riser limit, head-room, circulation prefix) from a profile. `tools/make_fixtures.py` builds
  three generic buildings with it (cantilevered trays, a rotated stepped hillside block, a courtyard with battered walls). `tools/preview.py`
  draws plans and an isometric view and lists what it could not draw.
* **New rules:** `B-142` (nothing but slabs, footings, piles, walls, stairs, ramps, openings, terrain and reservation volumes below the
  lowest floor), `B-143` (open-air rooms are `EXTERNAL` with `Enclosed` false), `B-144` (sloped roofs and leaning walls are modelled as
  such; review only).
* **Terrain extension** (`extensions.terrain`, off by default): `B-130` to `B-141` and `X-23`. The terrain source stays authoritative; the
  file carries a derived, read-only terrain element built from a GeoTIFF height patch and its sidecar, a georeference to a named custom CRS
  (with the building azimuth), the site elevation, water as metadata only, and a pinned source version that the package check compares with
  the sidecar, the site request and what the check report found in the master file. Rules inside the extension may be REQUIRED
  (`VERSIONING.md` now says so); `B-136` (float or bury) is an estimate and starts RECOMMENDED. Tools: `site_request.py`, `terrain_import.py`
  (error-bounded triangle network, strict GeoTIFF checks, size and triangle limits), `make_sample_terrain.py` (a plane or slope, for tests
  only), `terrain_lib.py`. Several levels may touch the ground (`GroundContact` per level) and the building may be turned from east. New
  profile parameters under `extensions.terrain` and `geometry.stairHeadroomMetres`, `geometry.roomOverlapToleranceMetres`; defaults for
  margins and tolerances are working values for each consumer to confirm.
* Schemas `terrain-patch` and `site-request`; the manifest gains the file roles `terrain-patch`, `terrain-sidecar`, `site-request` and a
  `terrain` section.
* Requirements are split: `requirements.txt` (core, now with shapely and lower bounds), `requirements-terrain.txt` (scipy),
  `requirements-preview.txt` (matplotlib). `MANIFEST.sha256` is now written by `gen_all.py --write`, checked by `test_sync.py` and built from
  the same file list (`tools/fileset.py`) as `MANIFEST.json` and the zip.

* **Release hygiene:** `tools/leakscan.py` (run by `test_sync.py`, with a seeded-leak check) fails when any file of the set, the hand-over
  files, the zip members or the PDF streams and links hold a local-file address or an absolute local path. `build_dist.py` now renders the PDF
  from a neutral folder and removes local-file link annotations (needs `requirements-dist.txt`); the 2.0.0 hand-over files are no longer
  shipped. Requirement files carry loose upper bounds.
* Hardening tests: an archway, a thick-wall archway and a too-high opening for `B-47`; malformed and disagreeing terrain pins for `X-23`;
  passing cases for `B-138` and `B-139` (`B-138` now reports a pass when the terrain is within its cap).

**Changed (existing rules whose checks behave differently; none can fail a delivery under the default profile)**

* `B-30`, `B-47`, `B-54` and the head-room half of `B-61` were review-only and are now automated as estimates (RECOMMENDED). Raising them
  to required in a profile is not advisable yet. `B-47` follows doors, stairs, open edges and empty through-openings in walls (an archway; the opening's sill must be within 0.7 m of the floor); `B-54` samples a grid of points in each room.
* `B-33` and `B-94` now skip open-air rooms. Their text already said "enclosed room"; the checker had applied them to every room.
* `B-115` keeps its meaning. The terrain extension is how a profile "says how"; a terrain element in a file whose profile does not enable the
  extension now warns. `B-110` and `B-120` leave the terrain element out (it has its own cap, `B-138`).
* `Enclosed` and `GroundContact` are now declaration properties (they must be single values).
* `how_to_check.method` in `rules.json` says "automated estimate" for the rules that approximate (`estimate` in `tools/rules_meta.json`).

**Fixed**

* `build_package.py verify` no longer crashes on a manifest whose terrain section holds a non-object; `X-23` reports it.
* `B-47` no longer reports a room behind an empty wall opening as unreachable.

* `gen_all.py` with no option no longer writes files; `llms.txt` states the real rule count (it said 179); `MANIFEST.sha256` was stale;
  `test_sync.py` now also checks the hand-written rule counts, each skill's rule range and the version.

## 2.0.0

The set was made portable: core practice is separated from consumer parameters.

* **Profiles.** New `profiles/` (`profile.schema.json`, `default.json`, `example-strict.json`). Every number or consumer-specific
  convention is now a profile parameter (`07-profile-parameters.md`). All checkers take `--profile`; reports name the profile used.
  `--brief` and the brief document are replaced by profiles; the manifest field `brief` is now `profile`.
* **Core vs extension.** Rules that only matter to consumers that walk people through rooms, turn fixtures into lights, generate signs
  or simplify furniture are extension rules (`walkability`, `luminaires`, `signboards`, `furnitureCollision`), off by default.
* **Rule levels** are defaults that a profile can raise, lower or switch off (`ruleLevels`). Changed defaults: `B-03`, `B-11`, `B-24`,
  `B-25`, `B-26`, `B-50`, `B-62`, `B-71`, `B-72`, `B-80`, `B-81`, `D-10`, `X-13` are now RECOMMENDED; `B-90` to `B-93`, `B-100`,
  `B-101`, `B-33`, `F-40`, `F-70` are REQUIRED only inside their extension; `B-04` now covers only ASCII (the one-line-per-entity part
  is new rule `B-08`).
* **New rules:** `B-08` (single-line entities, profile parameter), `X-14` (package size cap, profile parameter).
* **Rationales** rewritten in general interoperability terms (what goes wrong for any consumer). Reference values taken from one
  delivery were removed; numbers are profile parameters with defaults.
* **Defaults** changed to general values (for example `limits.maxFileMegabytes` 250, door clear height 2.0 m, stair riser 0.19 m,
  ramp slope 1:12) instead of one consumer's values; `example-strict.json` shows a tight consumer.
* **Mapper.** `tools/map_properties.py` is a generic rename tool driven by a mapping file, which may be a profile (`propertyNames`,
  `propertyValues`).
* **Docs.** New `ABOUT.md`, `VERSIONING.md`, `CONTRIBUTING.md`, `LICENSE.md` (CC BY 4.0 for prose, Apache-2.0 for code and
  machine-readable files, SPDX headers).
* **Tests.** `agent_harness.py` now runs against `default.json` and `example-strict.json`.

## 1.1.0

Agent-native layer: `rules.json`, skills, `AGENTS.md`, `llms.txt`, `llms-full.txt`, chunks, `MANIFEST.json`, `--json` on every tool,
`check_all.py`, `REPAIR-LOOP.md`, fresh-agent harness.

## 1.0.0

First release: four guides, a worked example, templates, schemas, checkers, a package builder and combined HTML and PDF.
