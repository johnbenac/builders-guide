---
name: accept-and-package-delivery
description: Package a delivery (master IFC, finish schedule, texture sets, items, tables, reports) with a manifest of SHA-256 hashes, versions, provenance and licences, run the final checks against a consumer profile, and decide whether to accept, ask for revision or reject someone else's delivery. Use when assembling or verifying a delivery package, writing manifest.json, choosing a version number, or when a check reports an X-rule finding.
license: CC-BY-4.0
metadata:
  version: "2.0.0"
  rules: "X-01 to X-60"
---

# Accept and package a delivery

## Inputs

* The finished parts: `ifc/` master, `finishes/`, `items/`, `tables/rooms.csv`, `tables/building.json`.
* The consumer's profile name and version, author organisation, licence terms, the version number.

## Procedure: packaging

1. **Layout.** Folder named `<id>-<version>/` with `ifc/`, `tables/`, `finishes/`, `items/`, `reports/`, `notes/`
   (`references/g4--1-what-you-send.md`). Exactly one master IFC under `ifc/` (X-13).
2. **Checks on the parts.** Run `check_all.py` on the master with the profile; write its report to `reports/check_ifc.json` (X-40).
   Repair per `REPAIR-LOOP.md` until zero REQUIRED findings.
3. **Notes.** `notes/changes.md` (X-32); `notes/open-points.md` for anything unsettled.
4. **Meta file.** `package-meta.json` from `templates/package-meta.template.json`: delivery id, title, SemVer version, UTC time such as
   `2026-10-22T10:00:00Z`, kind, author, profile (name, version), frame, a provenance entry per IFC file, texture set and item with source
   and licence, a licence statement, the checks block (X-10, X-20, X-21, X-30).
5. **Manifest.** `python3 tools/build_package.py init PACKAGE_DIR package-meta.json` writes `manifest.json` and `SHA256SUMS.txt`.
6. **Verify.** `python3 tools/check_all.py PACKAGE_DIR --profile PROFILE.json --json --out final.json` must exit 0. Never edit a file
   after this without rebuilding the manifest and rerunning (X-11, X-50).

## Procedure: accepting a delivery

1. Run `python3 tools/check_all.py PACKAGE_DIR --profile PROFILE.json --json`. A hash mismatch, an unreadable file, a wrong schema
   or units, a hard limit exceeded, a missing licence, or work built to the wrong profile means **reject** (give the reason).
2. Any other REQUIRED failure: **revision needed**; send the findings (`rule`, `level`, `location.element`, `message`, `fix_hint`) back.
3. No REQUIRED failure: review what scripts only estimate (B-33, B-61, B-101, B-102), finishes and wrap, lighting, clearances.
   **Accepted** or **accepted with notes** (list the RECOMMENDED findings).
4. Record the master file's hash with the outcome (`references/g4--7-how-a-receiving-party-accepts-returns-or-refus.md`).
5. If the consumer needs its own property names, rename with `python3 tools/map_properties.py in.ifc out.ifc --mapping CONSUMER_PROFILE.json`.

## Version numbers

PATCH: corrections, no identifier changes. MINOR: additions, existing identifiers unchanged. MAJOR: renamed, removed or re-meant
identifiers, or a changed frame (X-31). Never change a delivered version in place (X-50).

## Commands

```
python3 tools/build_package.py init PACKAGE_DIR package-meta.json
python3 tools/check_all.py PACKAGE_DIR --profile PROFILE.json --json --out final.json
python3 tools/build_package.py verify PACKAGE_DIR --profile PROFILE.json --json
```

## Reading the report

`build_package.py` findings: X-10 manifest schema, X-11 hash or size mismatch, X-12 unlisted file, X-13 master count, X-14 package size
cap, X-20 and X-21 provenance and licence, X-30 version and time form, X-40 the check report belongs to the master and passed.

## Stop conditions

* A licence or source is unknown: do not package; ask.
* A hash mismatch you did not cause: stop; do not rebuild over it without finding why.
* Same finding after three runs: report it.

## Definition of done

Packaging: `check_all.py PACKAGE_DIR` exits 0, `summary.requiredFailures` 0. Accepting: an outcome (accepted, accepted with notes,
revision needed, rejected) with its findings and the master file's hash.

## References (load on demand)

| Topic | File |
|---|---|
| all rules of this skill with fix hints | `references/rules.md` |
| layout and manifest | `references/g4--1-what-you-send.md`, `references/g4--3-the-manifest.md` |
| versions | `references/g4--4-versions.md` |
| checks (yours and a receiver's) | `references/g4--5-acceptance-checks.md` |
| checklist | `references/g4--6-pre-submission-checklist.md` |
| outcomes and revision | `references/g4--7-how-a-receiving-party-accepts-returns-or-refus.md` |
