<!-- chunk: sub--the-path-of-a-delivery | source: 08-submissions-and-ingest.md | title: The path of a delivery | rules: - -->
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
