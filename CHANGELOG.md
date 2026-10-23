<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Changelog

Format: newest first. See `VERSIONING.md` for what each kind of change means.

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

**Changed (existing rules whose checks behave differently; none can fail a delivery under the default profile)**

* `B-30`, `B-47`, `B-54` and the head-room half of `B-61` were review-only and are now automated as estimates (RECOMMENDED). Raising them
  to required in a profile is not advisable yet. `B-47` follows doors, stairs and open edges; `B-54` samples a grid of points in each room.
* `B-33` and `B-94` now skip open-air rooms. Their text already said "enclosed room"; the checker had applied them to every room.
* `B-115` keeps its meaning. The terrain extension is how a profile "says how"; a terrain element in a file whose profile does not enable the
  extension now warns. `B-110` and `B-120` leave the terrain element out (it has its own cap, `B-138`).
* `Enclosed` and `GroundContact` are now declaration properties (they must be single values).
* `how_to_check.method` in `rules.json` says "automated estimate" for the rules that approximate (`estimate` in `tools/rules_meta.json`).

**Fixed**

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
