<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# About this set

## What it is

A set of plain-language guides, rules, checkers and examples for making **IFC** files (the building-data format published by
buildingSMART International) that work in many different programs: viewers, simulators, game runtimes, BIM tools and archives. It
covers buildings, finishes (materials and wall coverings), furniture libraries, and the packaging and acceptance of deliveries.

It is **independent**. It is not endorsed by, affiliated with or certified by buildingSMART International or any standards body, and it
claims no conformance to any standard. The IFC specification itself is published by buildingSMART International
(https://www.buildingsmart.org/standards/bsi-standards/industry-foundation-classes/); this set is practical advice on top of it.

## Who it is for

* **Authors**: architects, modellers, interior decorators, furniture designers, and the software agents that do their work, who want
  their files to survive contact with other people's tools.
* **Consumers**: anyone who receives IFC deliveries and wants authors to build to their needs without a meeting.
* **Reviewers and archivists**: people who check, accept or return deliveries and want findings that point at exact elements.

## How it is organised

The set separates **core practice** from **consumer parameters**.

* **Core** is what is good practice for any consumer: a declared unit, a stated frame, levels, rooms with real floors, doors that
  fill openings, unique identifiers, honest materials, a manifest with hashes and licences. Core rules say *what goes wrong for any
  consumer* if you ignore them.
* **Parameters** are everything numeric or consumer-specific: size and triangle limits, identifier lengths, clearance values, whether
  room identifiers are mandatory, which optional extensions apply. They live in a **profile**, a small JSON file
  (`profiles/profile.schema.json`). `profiles/default.json` has publicly defensible defaults; `profiles/example-strict.json` shows a
  constrained consumer. Rules in `rules.json` name the parameters they use.
* A **consumer profile** is simply a profile a consumer publishes. Authors and agents build to it and check against it:
  `python3 tools/check_all.py PATH --profile consumer.json --json`. Reports state which profile they used.

## How a consumer adopts it

1. Copy `profiles/default.json` to `my-consumer.json`; set `name` and `version`.
2. Change the numbers that differ for you: `limits`, `budgets`, `identifiers`, `geometry`, `frame`, `buildVolume`, `keepOut`.
3. If your reader looks for particular property names or values, list them in `propertyNames` and `propertyValues`. Authors keep the
   neutral names; `python3 tools/map_properties.py in.ifc out.ifc --mapping my-consumer.json` renames them for you.
4. Make rules stricter (or switch them off) in `ruleLevels`; for example make `B-26` (room identifiers) `required`.
5. Switch on the extensions you implement: `walkability`, `luminaires`, `signboards`, `furnitureCollision`.
6. Validate the file against `profiles/profile.schema.json` and publish it at a stable address. Tell authors its name and version.
7. When you receive a delivery, run `check_all.py` with your profile; send findings back as they are (rule, element, fix hint).

## What it does not do

It does not define a new standard, certify anything, simulate physical behaviour, or replace the IFC documentation. Static files
only: nothing here needs a network or a service.

See [README.md](README.md) for the index, [VERSIONING.md](VERSIONING.md) for how the set changes, and
[CONTRIBUTING.md](CONTRIBUTING.md) to propose changes.
