<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Authoring Guide Set for IFC Buildings, Materials and Furniture

Version 2.3.0 (2026-10-23). Application-neutral guides, rules, checkers and examples for people and software agents who create
digital buildings, finishes, wall coverings and furniture in the IFC building-data format, so that their work can be used by many
different programs. Start with [ABOUT.md](ABOUT.md): what this is, who it is for, and how a consumer adopts it.

In these guides **the consumer** is whatever program or person receives your delivery (a viewer, a simulator, a game runtime, a BIM
tool, an archive). **A profile** is the small JSON file a consumer publishes with its numbers and conventions; if you have none, use
`profiles/default.json`. Everything else is in these guides.

## Core and profile

* **Core rules** say what is good practice for any consumer and what goes wrong for any consumer if you ignore it.
* **Profile parameters** hold everything numeric or consumer-specific: size and triangle limits, identifier lengths, clearances,
  property names, whether room identifiers are mandatory, and which optional extensions apply. See
  [07-profile-parameters.md](07-profile-parameters.md).
* **Extensions** (`walkability`, `luminaires`, `signboards`, `furnitureCollision`, `terrain`) are optional rule groups a profile switches on.

Check anything against a profile: `python3 tools/check_all.py PATH --profile consumer.json --json`. Reports name the profile used.

## For agents

The set is also written to be read and run by software agents of any kind. Static files only; no service is needed.

| File | Use |
|---|---|
| [AGENTS.md](AGENTS.md) | short entry point: what the set is, commands, working rules |
| `llms.txt`, `llms-full.txt` | index of the set, and all content in marked chunks |
| `skills/` | six skills (orient, author-building, decorate-interior, author-furniture-library, accept-and-package-delivery, submit-delivery), each with a short `SKILL.md` and on-demand `references/` |
| `rules.json` | all rules with level, applies_to, parameters, extension, how to check, fix hint, examples |
| [REPAIR-LOOP.md](REPAIR-LOOP.md) | run, read findings, fix, rerun until no REQUIRED finding remains |
| `profiles/` | the profile schema, the default profile, and an example of a strict consumer profile |
| `chunks/`, `MANIFEST.json` | the guides in pieces of about 1,500 tokens or less; every file with purpose and tags |
| `schemas/` | JSON Schemas: profile, rules, checker report, delivery manifest, submission block, proof manifest, catalogue, material library, furniture item, building summary, finish schedule |

## The five guides

| # | File | Who it is for | What it settles |
|---|---|---|---|
| 1 | [01-builders-and-architects-guide.md](01-builders-and-architects-guide.md) | architects, builders, modellers | file and schema, units, axes, levels, rooms, walls, floors, stairs, doors, openings, identifiers, property sets, geometry hygiene, optional lighting and signs |
| 2 | [02-interior-decorators-guide.md](02-interior-decorators-guide.md) | decorators, material and texture authors | finishes, coverings, floors and ceilings, colour keys, finish schedule, texture sets, material libraries |
| 3 | [03-furniture-and-fixtures-guide.md](03-furniture-and-fixtures-guide.md) | furniture and fixture designers | item library format, pivots, dimensions, anchors, clearances, collision, variants, instancing |
| 4 | [04-delivery-and-acceptance-guide.md](04-delivery-and-acceptance-guide.md) | everyone who sends or receives | package layout, manifest with hashes, versions, provenance and licences, checklist, acceptance checks, outcomes |
| 5 | [05-worked-example.md](05-worked-example.md) | everyone | one room with a door, a window, a table, a wall covering and a light, with a generator script and checker |

## Submissions

The same repository takes outside deliveries as pull requests from forks: fork it, build the delivery in a branch of your fork under
`deliveries/<slug>/`, open a pull request against `main`. Acceptance is a merge to `main`; `tools/ingest.py` then turns the merged delivery into
component assets and a neutral catalogue. See [08-submissions-and-ingest.md](08-submissions-and-ingest.md) and
[CONTRIBUTING.md](CONTRIBUTING.md). Deliveries are not part of the guide set and are not in its hand-over files.

Also: [06-rules-index.md](06-rules-index.md) (every rule in one table, with counts), [07-profile-parameters.md](07-profile-parameters.md), [08-submissions-and-ingest.md](08-submissions-and-ingest.md),
[templates/](templates/) (starting files), [tools/](tools/) (scripts), [CHANGELOG.md](CHANGELOG.md), [VERSIONING.md](VERSIONING.md),
[CONTRIBUTING.md](CONTRIBUTING.md), [LICENSE.md](LICENSE.md).

## How rules are written

> **B-12 · REQUIRED** - The statement.
>
> **B-90 · REQUIRED · luminaires** - A statement that applies only in the named extension.

* **REQUIRED** means that without it a consumer is likely to refuse the file, lose the element, or read it wrongly, or (guide 4) that
  the delivery process requires it. A delivery that breaks a REQUIRED rule is sent back.
* **RECOMMENDED** means good practice that prevents a defect often seen or keeps work portable. A delivery that ignores it is accepted if
  everything REQUIRED passes, but the reviewer may ask for revision.
* The level shown is the **default**. A profile can raise, lower or switch off any rule (`ruleLevels`); `rules.json` and the checkers use
  the profile's level.
* Numbers are never in a rule's text as a requirement: they are profile parameters, written in `backticks` (`limits.maxTriangles`).

Identifier letters: **B** builders and architects, **D** decorators, **F** furniture and fixtures, **X** delivery and acceptance.
Numbers are never reused; a retired rule keeps its number.

## Reading order

1. [ABOUT.md](ABOUT.md), then the vocabulary and profile sections of guide 1 (sections 1 and 2).
2. The guide for your role (1, 2 or 3).
3. Guide 4 before you package anything.
4. Guide 5 once, even if you only make furniture.

## Words used in a fixed sense

| Word | Meaning here |
|---|---|
| consumer | the program or person that receives and uses your delivery |
| profile | a consumer's published parameters (`profiles/profile.schema.json`) |
| delivery | everything you submit for one assignment (files, manifest, notes) |
| level | one horizontal floor of a building (an `IfcBuildingStorey`) |
| room | a named area with a floor, modelled as an `IfcSpace` (the IFC entity name; it always means "room or zone") |
| zone | a named volume that is data only (`IfcSpatialZone`) |
| volume | any three-dimensional extent |
| finish | the look of a surface (colour, texture, gloss) |
| item | one piece of furniture, fixture or accent |
| declaration property | a named property this set asks you to write; a profile can rename it |
| extension | an optional group of rules a profile switches on |

## Hand-over files

[dist/](dist/) holds the single-file versions:

| File | Content |
|---|---|
| `builders-guide-2.3.0.pdf` | all guides, the worked example, the submissions page and the rules index in one document |
| `builders-guide-2.3.0.html` | the same, as one web page |
| `builders-guide-2.3.0.zip` | the whole set, with `MANIFEST.sha256` |
| `SHA256SUMS.txt`, `builders-guide-2.3.0.zip.sha256` | SHA-256 of the three files above |

`MANIFEST.sha256` lists the SHA-256 of every other file in the set (`sha256sum -c MANIFEST.sha256`); `MANIFEST.json` describes the same files
with purpose and tags. `tools/build_dist.py` rebuilds all of this.

## What this set does not cover

* Structural, mechanical or electrical design content, and any simulation of how things move or work.
* Terrain. Ground relief is not carried in IFC here; a profile may say how it is supplied.
* Commercial terms between sender and receiver.
