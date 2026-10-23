<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# How submissions and ingest work

This repository holds the guide set and it is also where outside contributors offer **deliveries**: buildings, interiors, furniture,
materials, fixtures and hardware. A delivery is reviewed as a pull request. When the maintainers merge it, a separate tool turns the
accepted delivery into separate, content-addressed component assets and a neutral catalogue. This page is for people and for software
agents; the rules the automatic checks enforce are X-70 to X-78 in guide 4, section 8.

## The path of a delivery

1. **Fork** this repository (your own copy on the hosting service).
2. **Build** the delivery in a branch of your fork, in the folder `deliveries/<slug>/`. The slug is lower-case letters, digits and single
   hyphens, for example `oak-study`. Follow guides 1 to 4 and the worked example (guide 5); `deliveries/example-room/` is a small accepted-looking
   delivery to copy from.
3. **Check** it yourself: `python3 tools/check_all.py deliveries/<slug> --json` must exit 0 (this also runs `tools/check_submission.py`).
   `tools/ci/run_checks.sh <slug>` runs exactly what the automatic check runs.
4. **Open a pull request** from your branch against `main`. Fill in the checklist in the pull request template.
5. **Automatic check.** A workflow checks the changed delivery folders (see below). Fix every REQUIRED finding and push again.
6. **Review.** A maintainer reads the delivery. The checks cannot judge quality, ownership or fit, so a delivery that passes can still be
   declined or sent back with notes.
7. **Acceptance is a merge to `main`.** Nothing else counts as acceptance, and no tool takes in a delivery from a branch or a fork.
8. **Ingest** runs afterwards, on the merged commit (see "Ingest"). The commit hash is the provenance of everything it produces.

Only the folder `deliveries/<slug>/` should change in a delivery pull request. One delivery per pull request. A correction after
acceptance is a new pull request with a new version in the same folder (X-50: never edit a delivered version in place; add a new `delivery.version`).

## What a delivery folder holds

A delivery is an ordinary package (guide 4, section 1) with these differences:

```
deliveries/oak-study/
  delivery.json            the manifest (schemas/manifest.schema.json) plus a `submission` object (schemas/submission.schema.json)
  SHA256SUMS.txt           hashes of every file, as in any package
  ifc/<name>-master.ifc    the master IFC file, when the delivery has a building or room
  items/<itemId>/          furniture, fixtures and hardware as items (guide 3): <itemId>.ifc and <itemId>.item.json
  finishes/                finish schedule, library.json and textures/<set>/ (guide 2)
  previews/                pictures of the work (png or jpg) so a reviewer sees it first
  reports/ notes/ tables/  the check reports, the change notes and the room table, as in guide 4
```

`delivery.json` is built with `python3 tools/build_package.py init DIR meta.json --manifest-name delivery.json`; the meta file carries the
`delivery`, `author`, `profile`, `frame`, `provenance`, `licence` and `checks` parts of guide 4, section 3, and the `submission` object:

| Field | Content |
|---|---|
| `title`, `summary` | what the delivery is, in a sentence |
| `submitter.handle` | the account the pull request is opened from (no personal data is needed) |
| `licence` | `CC-BY-4.0` (the default), or `CC0-1.0` when the delivery says so; the profile lists the licences it takes |
| `profile` | name and version of the profile the delivery was checked against |
| `toolVersions` | the tools and libraries used (this guide set's version, the IFC library) |
| `attestation` | `ownWork`, `mayLicense`, `noRestrictedContent`, all `true` |

Contributed assets are offered under CC BY 4.0 unless the delivery states CC0. By opening the pull request the contributor attests that they
own the work or may license it, and that it contains no restricted third-party content (X-22, X-76).

## Limits

Defaults, all parameters of the profile (`submission` group, see `07-profile-parameters.md`): at most 200 files, 25 MiB per file, 100 MiB per
delivery; file types ifc, glb, png, jpg, json, md, csv and txt only (csv and txt exist because the room table and `SHA256SUMS.txt` need them);
no program, script, archive or executable file mode; no symbolic links; relative, portable, case-unique paths of at most 200 characters; images of
at most 64 million pixels. A consumer that accepts submissions can set other values in its own profile.

## The automatic check

`.github/workflows/check-delivery.yml` (a copy of the same steps without any workflow system is `tools/ci/run_checks.sh`) runs on pull requests
that touch `deliveries/**`. It installs the pinned requirements (`tools/requirements-ci.txt`), then for each changed delivery runs
`check_submission.py` and `check_all.py` under `profiles/default.json`, and again under `profiles/<name>.json` when `delivery.json` names a profile
that exists there. It uploads the JSON reports as an artifact, writes a summary to the run, and fails on any REQUIRED finding.

Pull requests from forks run with a read-only token and no secrets, and the workflow never uses `pull_request_target`. A first-time
contributor's run may wait until a maintainer approves it. A fork's token cannot write comments, so the result is the run summary and the
artifact; for pull requests from branches of this repository the workflow also posts the summary as a comment.

## Ingest

`python3 tools/ingest.py deliveries/<slug> --commit <merged commit hash> --out <output folder>` is run by a maintainer or an automation, on a
checkout of the merged commit of `main` (`--require-ancestor-of origin/main` makes it refuse anything else). It never uploads and uses no
network. In order, it:

1. copies the delivery (plain files only) to a temporary folder, with a time limit (`submission.ingestMaxSeconds`) and an optional memory limit;
2. re-runs `check_submission.py` and `check_all.py` on the copy, and refuses on any REQUIRED finding;
3. splits the delivery into **components**: each item under `items/`; from the master IFC each furniture element, covering (wall, floor or
   ceiling), fixture or luminaire assembly, hardware piece, door and window; each texture set as a material set;
4. exports each geometry component as a binary glTF (GLB, units metres, Y up) and reads it back to verify it;
5. stores every file as `blobs/sha256/<hash>.<ext>`; identical bytes (for example a table in `items/` and the same table in the master, or the
   same part in two deliveries) are stored once;
6. writes `catalogue/index.json` (one entry per distinct component, with every occurrence), `catalogue/deliveries/<slug>@<commit12>.json`
   and the handoff manifest `handoff/<slug>@<commit12>.json`, shaped by `schemas/catalogue.schema.json`.

Each component carries: kind and category; dimensions and bounds; the pivot (items keep the pivot their description declares, master elements are
moved to the centre of their footprint at their lowest point); anchors; the material references that link surface colours to the finish schedule and
to the material-set components; and, per occurrence, the delivery slug, commit hash, submitter, licence, source path and IFC identifier, and its
placement in the building file. The output depends only on the delivery bytes and the commit hash, so a second run gives the same bytes. `--dry-run` shows what
would be stored and what the output folder already holds, and writes nothing.

The handoff manifest lists the blobs to publish and the components with their files, licences and submitters. Publishing them anywhere is a
separate step owned by whoever runs the catalogue; this repository defines no destination.

Limits of this version: components from the master IFC are exported as GLB only (no per-component IFC file; item components also keep their source
IFC); walls, slabs, stairs and roofs are not components, only furnishing, coverings, fixtures, hardware, doors and windows; rotations are recorded
as an angle about the vertical axis; textures are carried as material sets and are not baked into the GLB.

## For agents

Harness-neutral steps; each command exits non-zero on failure. Replace `UPSTREAM` with the repository you were asked to contribute to.

```
gh repo fork UPSTREAM --clone --default-branch-only        # your fork, cloned; or fork in the web page
cd REPO && git checkout -b delivery-SLUG
pip install -r tools/requirements.txt
# build deliveries/SLUG/ (skills/submit-delivery/SKILL.md), then:
python3 tools/check_all.py deliveries/SLUG --json --out report.json   # exit 0 required
git add deliveries/SLUG && git commit -m "feat(deliveries): add SLUG" -m "What it is and what it was checked against."
git push -u origin delivery-SLUG
gh pr create --repo UPSTREAM --base main --title "Delivery: SLUG" --body-file .github/pull_request_template.md
```

Fill in the checklist honestly; do not tick the attestation boxes unless they are true, and do not set `attestation` fields to `true` for work you
cannot vouch for. Never edit tools, profiles or schemas in a delivery pull request. Stop and report if the same REQUIRED finding remains after
three runs (`REPAIR-LOOP.md`).
