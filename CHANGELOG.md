<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Changelog

Format: newest first. See `VERSIONING.md` for what each kind of change means.

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
