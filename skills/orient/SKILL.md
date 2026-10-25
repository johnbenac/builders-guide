---
name: orient
description: Start here when you are asked to create, check or hand over IFC buildings, interior finishes, wall coverings, furniture or fixtures for a consumer you cannot see (a viewer, simulator, game runtime, BIM tool or archive). Explains what the guide set is, how profiles carry consumer-specific numbers, which skill to load (author-building, decorate-interior, author-furniture-library, accept-and-package-delivery, submit-delivery), the commands, and the repair loop. Use it first whenever the task mentions IFC, a profile, a room table, a finish schedule, an item library or a delivery package.
license: CC-BY-4.0
metadata:
  version: "2.4.0"
  audience: any agent, any harness
---

# Orient

The set tells you how to build deliverables that many different consumers can use, and gives you tools that check them.
"The consumer" is whatever program or person will use your work; "the profile" is the small JSON file with its numbers and
conventions (`profiles/default.json` if it has none).

## Pick the skill

| The task is about | Load |
|---|---|
| a building: levels, rooms, walls, doors, windows, floors, stairs, optional lights, signs and terrain context | `skills/author-building/SKILL.md` |
| finishes: wall coverings, floors, ceilings, accents, texture sets, a material library | `skills/decorate-interior/SKILL.md` |
| furniture or fixtures as reusable items | `skills/author-furniture-library/SKILL.md` |
| packaging, versions, licences, final checks, accepting or sending back a delivery | `skills/accept-and-package-delivery/SKILL.md` |
| offering a delivery to the shared repository as a pull request from a fork, or how a merged one is ingested | `skills/submit-delivery/SKILL.md` |

A job with several parts: do the parts in this order, then package: building, finishes, items, package.

## Inputs you need before you start

1. The consumer's profile (shape: `profiles/profile.schema.json`; default: `profiles/default.json`). It gives limits, frame and level
   offset, identifier rules, allowed occupants, geometry values, build volume and keep-outs, and which optional extensions apply. If
   you have no profile, use the default and say so in your notes. If a value your work depends on is missing, ask the consumer;
   do not invent it.
2. Python 3 with the packages in `tools/requirements.txt` (`pip install -r tools/requirements.txt`).
3. The set's top folder. If your skill folder was copied away from the set, set `BUILDERS_GUIDE_ROOT` to that folder.

## Facts to keep in mind

* 214 rules in `rules.json`. Each has a default `level` (`required` or `recommended`), `applies_to`, `parameters` (profile values it
  uses), `extension` (null, or the optional group it belongs to), `statement`, `rationale`, `how_to_check`, `fix_hint`, `examples`.
  A profile can change levels (`ruleLevels`) and switch extensions on.
* Every checker takes `--profile FILE` and `--json` and prints one report (`schemas/check-report.schema.json`) that names the profile.
  Exit codes: 0 no REQUIRED failure, 1 at least one, 2 wrong command line, 3 unreadable input.
* One command checks anything: `python3 tools/check_all.py PATH --profile PROFILE.json --json`.
* Core practice: IFC in an accepted schema edition, in metres, Z up; rooms with real floors and stable identifiers; doors that fill
  openings; honest colours and a finish schedule; a manifest with hashes and licences.

## Procedure

1. Read the profile; list what you are asked to deliver; choose skills (table above).
2. Load the one skill you need now; load its `references/` files only when a step points to them.
3. Build, run `check_all.py`, then follow `REPAIR-LOOP.md` until no REQUIRED finding remains.
4. Package with the packaging skill and run `check_all.py` on the package folder.

## Stop conditions

* The profile lacks a value your work depends on: ask, then continue.
* The same finding stays after three repair runs: report it with what you tried.
* A REQUIRED rule conflicts with the profile: report the conflict; do not choose silently.

## Definition of done

`python3 tools/check_all.py PACKAGE_DIR --profile PROFILE.json --json` exits 0 with `summary.requiredFailures` equal to 0, and the
notes list any RECOMMENDED findings you left open.

## References

| Need | File |
|---|---|
| the loop in detail | `references/repair--the-loop.md`, `references/repair--stop-conditions.md` |
| what the set is and how a consumer adopts it | `references/about--what-it-is.md`, `references/about--how-a-consumer-adopts-it.md` |
| how rules are written | `references/readme--how-rules-are-written.md` |
| every profile parameter | `references/params--introduction-part-1-of-4.md` to `references/params--introduction-part-4-of-4.md` |

Run any tool from anywhere with `python3 scripts/run_tool.py TOOL ARGS`.
