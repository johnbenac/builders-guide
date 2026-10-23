<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Deliveries

This folder holds deliveries offered by contributors: buildings, interiors, furniture, materials, fixtures and hardware. It is **not part of
the guide set**: the guide's file list, manifest, zip and generated documents leave it out.

## How to add one

1. Fork the repository.
2. In a branch of your fork, create `deliveries/<slug>/` (slug: lower-case letters, digits and single hyphens). Copy the shape of
   `deliveries/example-room/`.
3. Run `python3 tools/check_all.py deliveries/<slug>` until it exits 0; `tools/ci/run_checks.sh <slug>` runs what the automatic check runs.
4. Open a pull request against `main`. Change only your delivery folder, and complete the checklist in the template.

Full description, with the layout, the `submission` fields, limits and what happens after a merge: `08-submissions-and-ingest.md`. For
software agents: `skills/submit-delivery/SKILL.md` (includes the `gh` commands).

## Terms

Contributed assets are offered under **CC BY 4.0** unless the delivery states **CC0** (`submission.licence` in `delivery.json`). By opening the
pull request you attest that you own the work or may license it, and that it contains no restricted third-party content. Keep the
attestation in `delivery.json` true.

## Rules of the folder

* One folder per delivery, one delivery per pull request, named by its slug; `delivery.id` equals the slug.
* Only data: ifc, glb, png, jpg, json, md (plus csv and txt for tables and checksums). No programs, scripts, archives or links.
* A merged version is never edited in place: put a correction in the same folder with a new `delivery.version` and new hashes, in a new pull
  request.
* Acceptance is a merge to `main`. The ingest tool (`tools/ingest.py`) runs on merged commits only and turns a delivery into components and a
  catalogue.

`example-room/` is a sample, rebuilt by `python3 tools/make_sample_delivery.py`.
