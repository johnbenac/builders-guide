<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Version policy

The set uses SemVer (`MAJOR.MINOR.PATCH`). The version is in `CHANGELOG.md`, in `rules.json` and in the names of the files in `dist/`.

## Rules never silently change meaning

* A rule's identifier (`B-41`) is never reused for a different rule. A retired rule keeps its number and is listed in the changelog.
* **PATCH**: wording fixes, clearer examples, better fix hints, tool bug fixes that do not change which deliveries pass or fail.
* **MINOR**: new rules (they start as `RECOMMENDED` unless a defect cannot be avoided any other way), new optional extensions, new
  profile parameters with defaults that keep existing deliveries passing, new tools, relaxed limits in `profiles/default.json`.
* **MAJOR**: a rule's meaning changes, a rule is retired or its default level is raised, a default limit is tightened, a profile or
  report format changes incompatibly, or a tool changes which deliveries pass.
* Every change that can alter a result is listed in `CHANGELOG.md` with the rule ids involved.

## Profiles

A profile has its own `version`. A consumer bumps it by the same rules: tightening a limit or raising a rule level is MAJOR for authors
who build to it. Reports record the profile name, version and hash, so a result can always be tied to the numbers it used.

## Deliveries

A delivery's version follows guide 4 (X-30 to X-31). A delivered version is never changed in place (X-50).

## Formats

`profile/1`, `check-report/1`, `rules/1`, `delivery-manifest/1`, `finish-schedule/1`, `item/1`, `material-library/1` and
`building-metadata/1` are format identifiers. An incompatible change gets a new number (`profile/2`) and a MAJOR release of the set.
