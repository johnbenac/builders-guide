<!-- Delivery pull request. Change only deliveries/<slug>/ in this pull request. Delete this line and the sections that do not apply. -->

## Delivery

* Folder: `deliveries/<slug>/`
* Title:
* What it is (building, interior, furniture, materials, fixtures, hardware):
* Profile it was checked against (name and version):
* Tools used and their versions:

## Checks

- [ ] `python3 tools/check_all.py deliveries/<slug>` exits 0 (this includes `tools/check_submission.py`).
- [ ] The reports in the delivery's `reports/` folder were made from the files as submitted.
- [ ] The proofs in `proofs/` were made by `python3 tools/build_proofs.py deliveries/<slug>` from the files as submitted, and `python3 tools/check_proofs.py deliveries/<slug> --reproduce` passes.
- [ ] A preview picture is in `previews/` (recommended).

## Licence and sign-off

- [ ] I offer this delivery under **CC BY 4.0**, or under **CC0** and `delivery.json` says so (`submission.licence`).
- [ ] I made this work, or I have the right to offer it, and I may license it under the licence above.
- [ ] It contains no third-party restricted content (no reproduced plans, models, textures or brand marks I have no permission to share).
- [ ] The file types and sizes follow the limits (no programs, scripts, archives or links).
- [ ] I understand that merging this pull request is the acceptance, that a maintainer may decline a delivery that passes every check, and that
      an accepted version is never changed in place (a correction is a new version).

## Notes for the reviewer

<!-- Anything unusual: open points, choices that need a decision, parts you could not settle (also list them in notes/open-points.md). -->
