<!-- chunk: sub--the-automatic-check | source: 08-submissions-and-ingest.md | title: The automatic check | rules: - -->
## The automatic check

`.github/workflows/check-delivery.yml` (a copy of the same steps without any workflow system is `tools/ci/run_checks.sh`) runs on pull requests
that touch `deliveries/**`. It installs the pinned requirements (`tools/requirements-ci.txt`), then for each changed delivery runs
`check_submission.py` and `check_all.py` under `profiles/default.json`, and again under `profiles/<name>.json` when `delivery.json` names a profile
that exists there; once under the default profile it also runs `check_proofs.py --reproduce` (it rebuilds the proofs on the runner, which has no graphics card) and
`validate_glb.py` with the pinned Khronos glTF Validator (installed by `npm ci`, no secret needed). It uploads the JSON reports as an artifact, writes a summary to the run, and fails on any REQUIRED finding.

Pull requests from forks run with a read-only token and no secrets, and the workflow never uses `pull_request_target`. A first-time
contributor's run may wait until a maintainer approves it. A fork's token cannot write comments, so the result is the run summary and the
artifact; for pull requests from branches of this repository the workflow also posts the summary as a comment.
