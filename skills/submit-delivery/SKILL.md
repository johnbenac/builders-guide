---
name: submit-delivery
description: Offer a building, interior, furniture item, material set, fixture or hardware piece to the shared repository as a pull request from a fork, with the automatic checks passing, or understand how an accepted (merged) delivery is ingested into component assets and a catalogue. Use when asked to contribute, submit or propose a delivery, to create deliveries/<slug>/, to write the submission block of delivery.json, to fix an X-70 to X-78 finding, or to run tools/ingest.py.
license: CC-BY-4.0
metadata:
  version: "2.2.0"
  rules: "X-70 to X-78"
---

# Submit a delivery

Contributors never push to the upstream repository. Fork it, build in a branch of your fork, open a pull request against `main`.
Acceptance is a merge to `main`; ingest runs only on merged commits.

## Inputs

* The upstream repository you were asked to contribute to, and a slug for the delivery (lower-case letters, digits, single hyphens).
* The finished work, built with the other skills (`author-building`, `decorate-interior`, `author-furniture-library`).
* The licence: `CC-BY-4.0` unless the delivery is to be `CC0-1.0`. You may only choose it if you own the work or may license it.

## Procedure

1. **Fork and branch.** `gh repo fork UPSTREAM --clone --default-branch-only`, then `git checkout -b delivery-SLUG`.
2. **Layout.** Create `deliveries/SLUG/` with `ifc/`, `items/`, `finishes/`, `previews/`, `reports/`, `notes/` as needed. Copy the
   shape of `deliveries/example-room/` (`references/sub--what-a-delivery-folder-holds.md`).
3. **Use only allowed files.** ifc, glb, png, jpg, json, md (plus csv and txt for tables and checksums). No scripts, programs, archives or
   links; relative lower-case names; keep within the limits (`references/sub--limits.md`, X-72 to X-75).
4. **Check the parts** with `check_all.py` on the master, finishes and items; repair per `REPAIR-LOOP.md`; write the reports into `reports/`.
5. **Manifest.** Write a meta file with `delivery.id` equal to the slug and a `submission` object (title, `submitter.handle`, `licence`,
   `profile`, `toolVersions`, `attestation` with the three fields true only if they are true). Then
   `python3 tools/build_package.py init deliveries/SLUG meta.json --manifest-name delivery.json`.
6. **Check the whole delivery.** `python3 tools/check_all.py deliveries/SLUG --json --out report.json` must exit 0; or
   `tools/ci/run_checks.sh SLUG` for what the automatic check runs.
7. **Pull request.** Commit only `deliveries/SLUG/`, push the branch to your fork,
   `gh pr create --repo UPSTREAM --base main --title "Delivery: SLUG" --body-file .github/pull_request_template.md`, and complete the checklist.
8. **After review.** Fix REQUIRED findings and push again. A maintainer merges; you do nothing else. Do not run ingest on your branch.

## Ingest (maintainers and automations)

`python3 tools/ingest.py deliveries/SLUG --commit MERGED_COMMIT --out OUT_DIR [--dry-run] [--require-ancestor-of origin/main]` re-runs the
checks, splits the delivery into components (items, furniture, coverings, fixtures, hardware, doors, windows, material sets), writes GLB files
and other blobs as `blobs/sha256/<hash>.<ext>`, `catalogue/index.json`, a delivery record and a handoff manifest. It never uploads. See
`references/sub--ingest.md`.

## Commands

```
python3 tools/check_submission.py deliveries/SLUG --json
python3 tools/check_all.py deliveries/SLUG --profile PROFILE.json --json --out report.json
tools/ci/run_checks.sh --base origin/main
python3 tools/ingest.py deliveries/SLUG --commit HASH --dry-run
```

## Reading the report

X-70 folder name, `delivery.id`, submission block; X-71 licence; X-72 file type or executable mode; X-73 counts and sizes; X-74 unsafe or
colliding path; X-75 link; X-76 attestation; X-77 file is not what its name says; X-78 no preview (a warning).

## Stop conditions

* You cannot truthfully make the attestation: do not submit.
* The same finding remains after three runs: report it with what you tried.
* The change would touch files outside `deliveries/SLUG/`: stop; delivery pull requests change only their own folder.

## Definition of done

`check_all.py deliveries/SLUG` exits 0 with `summary.requiredFailures` equal to 0, the branch is pushed to your fork, and a pull request
against `main` is open with the checklist completed. The pull request is not merged by its author.

## References (load on demand)

| Topic | File |
|---|---|
| rules X-70 to X-78 with fix hints | `references/rules.md` |
| how it all works, for agents too | `references/sub--the-path-of-a-delivery.md`, `references/sub--ingest.md` |
