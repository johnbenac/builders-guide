<!-- SPDX-License-Identifier: Apache-2.0 -->
# Tools

Scripts that let you check your own work the way the receiving party will. All are plain Python 3, print what they
checked, and exit with status 1 when a REQUIRED rule fails.

Install once: `pip install -r tools/requirements.txt` (IFC reading, arrays, images, JSON schema checks).

| Script | Use |
|---|---|
| `check_all.py` | one entry point: runs every check that applies to a master file, a finishes folder, an items folder or a package, and prints one report (`--json`, `--out`) |
| `check_ifc.py` | acceptance checks for a master IFC file (guide 4, section 5). Options: `--profile`, `--finish-schedule`, `--level-offset`, `--known-room-ids`, `--report`, `--json` |
| `check_texture_set.py` | checks for one texture set folder (guide 2, section 4); `--preview` writes a three-by-three wrap picture |
| `check_item.py` | checks for one library item folder (guide 3) |
| `build_package.py` | `init` writes the manifest and checksum file; `verify` runs the package checks (guide 4) |
| `map_properties.py` | consumer intake: renames declaration properties between the neutral names and a consumer's names, using a mapping file the receiving party keeps outside this set (`--reverse` undoes it). `test_map_properties.py` tests it |
| `make_sample.py`, `make_sample_item.py`, `make_sample_texture_set.py` | generate the pieces of the worked example (guide 5) |
| `run_example.py` | builds, checks and packages the whole worked example in one go |
| `selftest.py` | builds the worked example, breaks it eleven ways, tests the property mapper, the generated files and the agent harness and confirms the checker names the right rule each time |
| `rules_index.py` | regenerates `06-rules-index.md` and cross-checks every rule id used in the guides and scripts |
| `build_dist.py` | builds the combined HTML and PDF and the zip with its checksums |
| `gen_all.py` | writes or checks every generated file: `rules.json`, `chunks/`, `llms.txt`, `llms-full.txt`, `skills/*/references/`, `06-rules-index.md`, `MANIFEST.json` |
| `rules_meta.json` | machine fields of the rules (rationale, fix hint, examples, related, which tool checks them); with the guides it is the source of `rules.json` |
| `test_sync.py` | fails if the guides and the generated files differ, or a skill, link or hash is wrong |
| `agent_harness.py` | simulates a fresh agent: builds a building, a material library, an item and a package from the set alone, repairs one finding, then breaks each rule category and checks the findings |
| `report.py` | shared report format |

Report format (`schemas/check-report.schema.json`): `schema`, `tool`, `toolVersion`, `target`, `result` (`pass`, `fail`, `error`),
`exitCode`, `summary`, `findings`. Every finding has a stable `id`, `rule`, `level`, `status` (`pass`, `info`, `warn`, `fail`),
`severity`, `location` (`file`, `element` = the product's `GlobalId`), `message` and, on `warn` and `fail`, `fix_hint`.
Exit codes: 0 no REQUIRED failure, 1 at least one, 2 wrong command line, 3 unreadable input.
