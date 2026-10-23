<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# AGENTS.md

This folder is an application-neutral guide set for making IFC buildings, finishes (materials, wall coverings) and furniture that
many different consumers (viewers, simulators, game runtimes, BIM tools, archives) can use. It is meant to be read and run by agents;
people can read the PDF or HTML in `dist/`. Everything is static files and Python scripts: no service, no network.

## Start here

1. Read `skills/orient/SKILL.md` (about 70 lines). It tells you which skill to load.
2. Load only the skill you need: `skills/author-building`, `skills/decorate-interior`, `skills/author-furniture-library`,
   `skills/accept-and-package-delivery`, `skills/submit-delivery`. Each skill points to small files under its `references/` for detail.
3. Rules are in `rules.json` (206, stable ids like `B-41`). Each has a default `level`, `statement`, `rationale`, `parameters`,
   `extension`, `how_to_check`, `fix_hint`, `examples`, `related`.
4. Consumer-specific numbers are in a **profile** (`profiles/profile.schema.json`; default `profiles/default.json`). Build and check
   against the consumer's profile when you have one.
5. Find everything else through `llms.txt` (index) or `MANIFEST.json` (every file with purpose and tags).

## Commands

```
pip install -r tools/requirements.txt                        # core; add -r tools/requirements-terrain.txt or -preview.txt for those tools
python3 tools/check_all.py PATH --profile PROFILE.json --json --out report.json   # PATH: .ifc file, finishes/ folder, items/ folder, or package folder
python3 tools/make_sample.py work/                            # a complete valid example to copy from
python3 tools/map_properties.py in.ifc out.ifc --mapping PROFILE.json   # rename declaration properties to a consumer's names
python3 tools/site_request.py MASTER.ifc --floor-elevation H --origin E N --out site-request.json   # only if the profile enables terrain: what the building sends its terrain source
python3 tools/terrain_import.py patch.tif patch.json MASTER.ifc --request site-request.json --out OUT.ifc   # only if the profile enables terrain: add the derived terrain patch
python3 tools/make_fixtures.py fixtures/                      # three larger worked buildings, built with tools/ifc_author.py
python3 tools/preview.py MASTER.ifc preview/                  # plans and an isometric view, to see your own work
python3 tools/run_example.py example-out                      # build, check and package the example end to end
python3 tools/selftest.py                                     # prove the checkers still catch every deliberate fault
python3 tools/agent_harness.py                                # prove a fresh agent can pass using only this set, under two profiles
python3 tools/check_submission.py deliveries/SLUG --json      # form checks of a submitted delivery (X-70 to X-78); check_all.py runs them too
python3 tools/ingest.py deliveries/SLUG --commit HASH --out OUT --dry-run   # maintainers: split a MERGED delivery into components and a catalogue
python3 tools/test_submission.py                              # prove the submission checks and ingest still behave
python3 tools/gen_all.py --write                              # regenerate rules.json, chunks, llms files, references, MANIFEST.json
```

Exit codes of every checker: 0 no REQUIRED failure, 1 at least one REQUIRED failure, 2 wrong command line, 3 unreadable input.

## Working rules

* Run the checker, read `findings`, fix the deliverable, rerun: `REPAIR-LOOP.md`. Stop after three runs with the same finding id,
  and report it.
* The profile supplies the numbers that differ between consumers (limits, frame, level offset, identifier rules, build volume, allowed
  `Occupant` strings, extensions). If one is missing and your work depends on it, ask; do not invent it.
* Never edit a report, a rule level or a tool to get a pass. Never change a delivered version in place.
* Generated files (`rules.json`, `chunks/`, `llms*.txt`, `skills/*/references/`, `MANIFEST.json`, `06-rules-index.md`,
  `07-profile-parameters.md`) come from the guides, `tools/rules_meta.json` and the profiles; edit those, then run
  `gen_all.py --write`. `python3 tools/test_sync.py` fails if they differ.
* To contribute a delivery, fork the repository, build it in a branch of your fork under `deliveries/<slug>/` and open a pull request against
  `main` (`skills/submit-delivery/SKILL.md`). Change only your delivery folder. Acceptance is a merge; ingest runs on merged commits only.
* Describe requirements as what any consumer needs ("the consumer", "the profile"). Do not name products, vendors or projects, and do
  not claim conformance to or endorsement by any standard or body.

## Layout

`skills/` skills; `tools/` scripts and `rules_meta.json`; `profiles/` profile schema, default and example; `schemas/` JSON Schemas;
`templates/` starting files; `chunks/` guide sections of about 1,500 tokens or less; `01`-`05` guides; `REPAIR-LOOP.md`; `ABOUT.md`;
`dist/` PDF, HTML, zip and checksums; `deliveries/` submitted deliveries (not part of the set or its hand-over files); `.github/` pull request template and workflow.
