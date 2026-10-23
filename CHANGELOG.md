<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Changelog

Format: newest first. See `VERSIONING.md` for what each kind of change means.

## Unreleased

Terrain context for consumers whose ground comes from their own terrain source (optional extension `terrain`, off by default).

* **New rules** `B-130` to `B-140` (guide 1, section 16) and `X-23` (guide 4): one derived, read-only terrain element, a valid
  heightfield, cover of the footprint, a georeference to a named custom CRS, site elevation, no building in water, no floating or
  buried building, a pinned source, a triangle cap, water as metadata only, a stated frame; the package pins the terrain source version.
* **Changed:** `B-115` now allows the terrain patch of the extension and forbids pads, cuts, fills and water in the file; `B-110` and
  `B-120` leave the terrain element out (it has its own cap).
* **Profile:** `extensions.terrain` (CRS name, error bound, margins, grading rule, sea level, float and bury tolerances, site elevation
  tolerance, triangle cap). Defaults for margins and tolerances are working values, to be confirmed by each consumer.
* **Tools:** `site_request.py`, `terrain_import.py`, `make_sample_terrain.py` (plane or slope, tests only), `terrain_lib.py`,
  `test_terrain.py`. New dependencies `scipy` and `shapely`.
* **Schemas:** `terrain-patch` (sidecar), `site-request`; the manifest gains the file roles `terrain-patch`, `terrain-sidecar`,
  `site-request` and a `terrain` section.
* `tools/gen_all.py` leaves the `work/` folder out of the manifest, and `llms.txt` states the real rule count.

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
