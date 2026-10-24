<!-- chunk: sub--for-agents | source: 08-submissions-and-ingest.md | title: For agents | rules: - -->
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
