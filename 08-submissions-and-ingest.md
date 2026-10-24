<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# How submissions and ingest work

This repository holds the guide set and it is also where outside contributors offer **deliveries**: buildings, interiors, furniture,
materials, fixtures and hardware. A delivery is reviewed as a pull request. When the maintainers merge it, a separate tool turns the
accepted delivery into separate, content-addressed component assets and a neutral catalogue. This page is for people and for software
agents; the rules the automatic checks enforce are X-70 to X-86 in guide 4, section 8 (X-79 to X-86 are the proofs, below).

## The path of a delivery

1. **Fork** this repository (your own copy on the hosting service).
2. **Build** the delivery in a branch of your fork, in the folder `deliveries/<slug>/`. The slug is lower-case letters, digits and single
   hyphens, for example `oak-study`. Follow guides 1 to 4 and the worked example (guide 5); `deliveries/example-room/` is a small accepted-looking
   delivery to copy from.
3. **Make the proofs** (`python3 tools/build_proofs.py deliveries/<slug>`, see "Proofs" below), refresh the manifest, then **check** it yourself:
   `python3 tools/check_all.py deliveries/<slug> --json` must exit 0 (this also runs `tools/check_submission.py` and `tools/check_proofs.py`).
   `tools/ci/run_checks.sh <slug>` runs exactly what the automatic check runs, including the rebuild of the proofs.
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
  proofs/                  GLB exports, their validation report, the standard renders and manifest.json (made by tools/build_proofs.py)
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

## Proofs

Every submitted delivery carries **proofs**: models and pictures that anyone can look at without a modelling program, and rebuild to see that
they are honest. `python3 tools/build_proofs.py deliveries/<slug>` makes all of them from the delivered files, in three steps, and writes
`proofs/manifest.json` (`schemas/proofs.schema.json`, format `proofs/1`):

1. **Export** (`tools/export_glb.py`): `proofs/glb/model.glb` (the whole master IFC as a scene graph: `model` > `level:<name>` >
   `<kind>:<name>#<GlobalId>`), `proofs/glb/components/*.glb` (one per item and per furniture element, covering, fixture or luminaire
   assembly, hardware piece, door and window, exactly the GLB `ingest.py` stores for it) and `proofs/glb/materials/*.glb` (a 2 x 2 swatch of each
   texture set with its maps embedded). Units are metres and the axes are Y up: an IFC point (x, y, z) becomes (x, z, -y). Colours are PBR
   metallic-roughness materials. The files are deterministic and hold no path, time, user or host.
2. **Validate** (`tools/validate_glb.py`): structure (container, indices, accessors, images, materials, scene graph, nothing unused, no URI),
   conventions (units and axis note, generator, size, unit-length normals, tangents with a normal map, node names), the profile's budgets, and
   with `--ifc` each product's bounding box against the IFC file. The Khronos glTF Validator (Apache-2.0, pinned in
   `tools/khronos/package-lock.json`, `npm ci --prefix tools/khronos`) is run as well when it is installed. The report is
   `proofs/reports/glb-validation.json` (`check-report/1`, rule X-80).
3. **Render** (`tools/render.py`), from the GLB files only: a plan for each level (cut at 1.2 m), four interior views for each room kind
   present (kind = the room's `Function` property; the first two rooms of a kind by identifier), four exterior views, and a contact sheet of
   eight turntable frames for every component (four fixed frames for a texture swatch).

The renderer is a software rasteriser in numpy (about 400 lines): no graphics card, display, browser or system library, so the same GLB gives
the same picture on a laptop and on a hosted runner. It draws flat-shaded triangles with a z-buffer, 2 x 2 supersampled, with base colours and
the base colour texture; it does not draw normal maps, metal, roughness, shadows or reflections. The lighting, background, camera and sizes are
fixed conventions, recorded for every picture (`tools/render.py` states them). A headless browser with a bundled viewer library, or Blender, would draw
nicer pictures, but they depend on a graphics stack that differs between machines, so the same file would not give the same picture; the
choice favours reproducibility over beauty. (Tried while choosing: headless Chromium with software WebGL runs here and repeats itself on one machine, but needs a browser, a
vendored viewer library of some hundreds of kilobytes, and gives pixels that depend on the browser and graphics-layer build; Blender is optional
high-quality software that is far larger than this repository and, with a graphics card, differs from machine to machine.) The manifest records, for every GLB, its SHA-256, size and source IFC hash, and for every picture
its path, SHA-256, pixel size, camera, light, the hash of the GLB it was made from and the tool and version.

`python3 tools/check_proofs.py deliveries/<slug>` checks the manifest against the files (X-79), the GLB files against their sources and the
validation report (X-81, X-80), the coverage of the pictures (X-82), the traceability of each picture to a delivered GLB (X-83), the size limits
(X-84) and the metadata of every image and GLB (X-85); with `--reproduce` it also rebuilds the GLB files, compares the bytes, re-renders every
picture from the delivered GLB and compares it within `proofs.renderTolerance` (X-86). Where the toolchain is not available it says so (an
`info` finding) and skips; it never reports a skipped check as passed. Make the proofs again after any change to an IFC file, item or texture set.

## Limits

Defaults, all parameters of the profile (`submission` and `proofs` groups, see `07-profile-parameters.md`): at most 600 files (proofs add a GLB and a sheet for every component; it was 200 before 2.3.0), 25 MiB per file, 100 MiB per
delivery; file types ifc, glb, png, jpg, json, md, csv and txt only (csv and txt exist because the room table and `SHA256SUMS.txt` need them);
no program, script, archive or executable file mode; no symbolic links; relative, portable, case-unique paths of at most 200 characters; images of
at most 64 million pixels; renders of at least 256 and at most about 2 million pixels and 3 MiB, and `proofs/` of at most 64 MiB. A consumer that accepts submissions can set other values in its own profile.

## The automatic check

`.github/workflows/check-delivery.yml` (a copy of the same steps without any workflow system is `tools/ci/run_checks.sh`) runs on pull requests
that touch `deliveries/**`. It installs the pinned requirements (`tools/requirements-ci.txt`), then for each changed delivery runs
`check_submission.py` and `check_all.py` under `profiles/default.json`, and again under `profiles/<name>.json` when `delivery.json` names a profile
that exists there; once under the default profile it also runs `check_proofs.py --reproduce` (it rebuilds the proofs on the runner, which has no graphics card) and
`validate_glb.py` with the pinned Khronos glTF Validator (installed by `npm ci`, no secret needed). It uploads the JSON reports as an artifact, writes a summary to the run, and fails on any REQUIRED finding.

Pull requests from forks run with a read-only token and no secrets, and the workflow never uses `pull_request_target`. A first-time
contributor's run may wait until a maintainer approves it. A fork's token cannot write comments, so the result is the run summary and the
artifact; for pull requests from branches of this repository the workflow also posts the summary as a comment.

## Ingest

`python3 tools/ingest.py deliveries/<slug> --commit <merged commit hash> --out <output folder>` is run by a maintainer or an automation, on a
checkout of the merged commit of `main` (`--require-ancestor-of origin/main` makes it refuse anything else). It never uploads and uses no
network. In order, it:

1. copies the delivery (plain files only) to a temporary folder, with a time limit (`submission.ingestMaxSeconds`) and an optional memory limit;
2. re-runs `check_submission.py` and `check_all.py` on the copy (the latter includes the stored-file checks of the proofs), and refuses on any REQUIRED finding;
3. splits the delivery into **components**: each item under `items/`; from the master IFC each furniture element, covering (wall, floor or
   ceiling), fixture or luminaire assembly, hardware piece, door and window; each texture set as a material set;
4. exports each geometry component as a binary glTF (GLB, units metres, Y up) and reads it back to verify it;
5. stores every file as `blobs/sha256/<hash>.<ext>`; identical bytes (for example a table in `items/` and the same table in the master, or the
   same part in two deliveries) are stored once;
6. compares the contributor's proofs with a fresh export from the delivered files (GLB hashes, render hashes, and that every component GLB of the
   ingest is among the proofs) and reports any mismatch in the result; the ingest result stays authoritative and nothing is refused for it. Each
   component links the contact sheet of its GLB (`proof-render` file), and the delivery record lists every render and the GLB files;
7. writes `catalogue/index.json` (one entry per distinct component, with every occurrence), `catalogue/deliveries/<slug>@<commit12>.json`
   and the handoff manifest `handoff/<slug>@<commit12>.json`, shaped by `schemas/catalogue.schema.json`.

Each component carries: kind and category; dimensions and bounds; the pivot (items keep the pivot their description declares, master elements are
moved to the centre of their footprint at their lowest point); anchors; the material references that link surface colours to the finish schedule and
to the material-set components; and, per occurrence, the delivery slug, commit hash, submitter, licence, source path and IFC identifier, and its
placement in the building file. The output depends only on the delivery bytes and the commit hash, so a second run gives the same bytes. `--dry-run` shows what
would be stored and what the output folder already holds, and writes nothing.

The handoff manifest lists the blobs to publish and the components with their files, licences and submitters. Publishing them anywhere is a
separate step owned by whoever runs the catalogue; this repository defines no destination.

Limits of this version: the renders show base colours and one texture (no normal maps, metal or roughness); a texture set is shown as a swatch, not on a wall; components from the master IFC are exported as GLB only (no per-component IFC file; item components also keep their source
IFC); walls, slabs, stairs and roofs are not components, only furnishing, coverings, fixtures, hardware, doors and windows; rotations are recorded
as an angle about the vertical axis; textures are carried as material sets and are not baked into the GLB.

## For agents

Harness-neutral steps; each command exits non-zero on failure. Replace `UPSTREAM` with the repository you were asked to contribute to.

```
gh repo fork UPSTREAM --clone --default-branch-only        # your fork, cloned; or fork in the web page
cd REPO && git checkout -b delivery-SLUG
pip install -r tools/requirements.txt
# build deliveries/SLUG/ (skills/submit-delivery/SKILL.md), then:
python3 tools/build_proofs.py deliveries/SLUG                         # GLB files, validation report, renders, manifest; then refresh delivery.json
python3 tools/check_all.py deliveries/SLUG --json --out report.json   # exit 0 required
git add deliveries/SLUG && git commit -m "feat(deliveries): add SLUG" -m "What it is and what it was checked against."
git push -u origin delivery-SLUG
gh pr create --repo UPSTREAM --base main --title "Delivery: SLUG" --body-file .github/pull_request_template.md
```

Fill in the checklist honestly; do not tick the attestation boxes unless they are true, and do not set `attestation` fields to `true` for work you
cannot vouch for. Never edit tools, profiles or schemas in a delivery pull request. Stop and report if the same REQUIRED finding remains after
three runs (`REPAIR-LOOP.md`).
