---
name: submit-delivery
description: Offer a building, interior, furniture item, material set, fixture or hardware piece to the shared repository as a pull request from a fork, with the automatic checks passing, or understand how an accepted (merged) delivery is ingested into component assets and a catalogue. Use when asked to contribute, submit or propose a delivery, to create deliveries/<slug>/, to write the submission block of delivery.json, to make or fix the proofs (GLB files, validation report, renders, proofs/manifest.json), to fix an X-70 to X-86 finding, or to run tools/ingest.py.
license: CC-BY-4.0
metadata:
  version: "2.3.0"
  rules: "X-70 to X-86"
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
2. **Layout.** Create `deliveries/SLUG/` with `ifc/`, `items/`, `finishes/`, `previews/`, `reports/`, `notes/` as needed (`proofs/` is made for you, step 5). Copy the
   shape of `deliveries/example-room/` (`references/sub--what-a-delivery-folder-holds.md`).
3. **Use only allowed files.** ifc, glb, png, jpg, json, md (plus csv and txt for tables and checksums). No scripts, programs, archives or
   links; relative lower-case names; keep within the limits (`references/sub--limits.md`, X-72 to X-75).
4. **Check the parts** with `check_all.py` on the master, finishes and items; repair per `REPAIR-LOOP.md`; write the reports into `reports/`.
5. **Proofs.** `python3 tools/build_proofs.py deliveries/SLUG` writes `proofs/`: GLB files of the whole model and of every component, a GLB
   validation report, the standard renders and `proofs/manifest.json` (see "Proofs" below). Do it after the last change to any IFC file, item or
   texture set, and never edit the output by hand.
6. **Manifest.** Write a meta file with `delivery.id` equal to the slug and a `submission` object (title, `submitter.handle`, `licence`,
   `profile`, `toolVersions`, `attestation` with the three fields true only if they are true). Then
   `python3 tools/build_package.py init deliveries/SLUG meta.json --manifest-name delivery.json`.
7. **Check the whole delivery.** `python3 tools/check_all.py deliveries/SLUG --json --out report.json` must exit 0; or
   `tools/ci/run_checks.sh SLUG` for what the automatic check runs.
8. **Pull request.** Commit only `deliveries/SLUG/`, push the branch to your fork,
   `gh pr create --repo UPSTREAM --base main --title "Delivery: SLUG" --body-file .github/pull_request_template.md`, and complete the checklist.
9. **After review.** Fix REQUIRED findings and push again. A maintainer merges; you do nothing else. Do not run ingest on your branch.

## Proofs

Every delivery carries proofs so that a reviewer sees the work without a modelling program and can rebuild the pictures to see that they are honest
(rules X-79 to X-86, `references/sub--proofs.md`). The tools need no graphics card, display or browser.

* `tools/export_glb.py` writes `proofs/glb/model.glb` (scene graph `model` > `level:<name>` > `<kind>:<name>#<GlobalId>`), one GLB per item, furniture
  element, covering, fixture, hardware piece, door and window under `proofs/glb/components/`, and a swatch per texture set under `proofs/glb/materials/`.
  Units are metres, axes Y up, `(x, y, z) -> (x, z, -y)` from the IFC frame; deterministic bytes; no paths or times.
* `tools/validate_glb.py` checks structure and conventions, bounding boxes against the IFC file and (when `npm ci --prefix tools/khronos` has been run)
  the Khronos glTF Validator; the report is `proofs/reports/glb-validation.json` and must pass.
* `tools/render.py` draws, from the GLB files only: a plan per level, four interior views for each room kind present (a room needs a `Function`
  property), four exterior views, and a contact sheet of turntable frames for every component. Fixed light, background and sizes.
* `proofs/manifest.json` lists every GLB (SHA-256, size, source IFC hash), the validation report and every picture (path, SHA-256, pixel size, camera,
  light, the hash of the GLB it was made from, tool and version) and a coverage statement.
* `python3 tools/check_proofs.py deliveries/SLUG --reproduce` checks all of it and rebuilds the GLB files and pictures to compare them; if the
  toolchain is missing it says "skipped", which is not a pass. A finding names its rule: X-79 manifest or stray file, X-80 a GLB problem (the finding's `code`
  says which), X-81 missing GLB or source changed or report failing, X-82 missing plan, room kind, exterior view or sheet, X-83 a picture not traceable to its
  GLB, X-84 size limits, X-85 metadata, X-86 not reproducible. Every one is fixed by running `build_proofs.py` again after fixing the source; none by editing a proof.

## Ingest (maintainers and automations)

`python3 tools/ingest.py deliveries/SLUG --commit MERGED_COMMIT --out OUT_DIR [--dry-run] [--require-ancestor-of origin/main]` re-runs the
checks, splits the delivery into components (items, furniture, coverings, fixtures, hardware, doors, windows, material sets), writes GLB files
and other blobs as `blobs/sha256/<hash>.<ext>`, `catalogue/index.json`, a delivery record and a handoff manifest, compares the delivery's proofs with a
fresh export (the ingest result stays authoritative; a mismatch is reported) and links each component to its contact sheet. It never uploads. See
`references/sub--ingest.md`.

## Commands

```
python3 tools/check_submission.py deliveries/SLUG --json
python3 tools/build_proofs.py deliveries/SLUG
python3 tools/check_proofs.py deliveries/SLUG --reproduce --json
python3 tools/check_all.py deliveries/SLUG --profile PROFILE.json --json --out report.json
tools/ci/run_checks.sh --base origin/main
python3 tools/ingest.py deliveries/SLUG --commit HASH --dry-run
```

## Reading the report

X-70 folder name, `delivery.id`, submission block; X-71 licence; X-72 file type or executable mode; X-73 counts and sizes; X-74 unsafe or
colliding path; X-75 link; X-76 attestation; X-77 file is not what its name says; X-78 no preview (a warning); X-79 to X-86 the proofs (above).

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
| rules X-70 to X-86 with fix hints | `references/rules.md` |
| how it all works, for agents too | `references/sub--the-path-of-a-delivery.md`, `references/sub--proofs.md`, `references/sub--ingest.md` |
