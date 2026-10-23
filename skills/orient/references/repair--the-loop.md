<!-- chunk: repair--the-loop | source: REPAIR-LOOP.md | title: The loop | rules: - -->
## The loop

1. **Run** one command for the deliverable, printing JSON:

   ```
   python3 tools/check_all.py PATH --json --out report.json
   ```

   (`PATH` is a master `.ifc` file, a folder with `finishes/`, a folder with `items/`, or a package folder with
   `manifest.json`. Add `--profile PROFILE.json` for a building so the frame, identifiers and volumes are checked.)
2. **Read** the report. Look at `result`, `exitCode` and `summary.requiredFailures` first. Then list the findings
   whose `status` is `fail`: each has `rule`, `message`, `location.element` (a `GlobalId`, when one product is
   concerned), `location.file` and `fix_hint`. For more on a rule, open its entry in `rules.json` (`statement`,
   `rationale`, `examples`, `related`).
3. **Fix** the source of the deliverable (the model, the schedule, the item, the package inputs), not the report.
   Fix the lowest-numbered structural findings first (`B-01` to `B-06`, `B-13`, `B-20` to `B-26`): later findings often
   disappear with them. Make one kind of change at a time.
4. **Rebuild** whatever the fix touched (re-export the IFC, rebuild the manifest with `build_package.py init`).
5. **Rerun** step 1 and compare. Repeat until `summary.requiredFailures` is 0 and the exit code is 0.

Then look at `warn` findings (RECOMMENDED rules). Fix the ones whose `fix_hint` is cheap; list the rest in
`notes/open-points.md`.
