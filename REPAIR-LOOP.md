<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Repair loop

How to get a deliverable to zero REQUIRED findings. The same loop works for a building, a material library, a
furniture library and a package. It needs only the tools in `tools/`; no network and no service.

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

## Report fields

| Field | Meaning |
|---|---|
| `result` | `pass`, `fail` or `error` |
| `exitCode` | `0` no REQUIRED rule failed; `1` at least one did; `2` wrong command line; `3` an input could not be read |
| `summary` | counts: `requiredFailures`, `recommendedWarnings`, `passes`, `info` |
| `findings[].id` | stable: the rule id, then a short hash of rule, file, element and message; the same problem keeps the same id between runs |
| `findings[].status` | `pass`, `info`, `warn` (RECOMMENDED not met) or `fail` (REQUIRED not met) |
| `findings[].fix_hint` | what to change, present on `warn` and `fail` |
| `reports[]` | the full report of each tool that `check_all.py` ran |

To list only what must be fixed, read the file with any JSON tool, for example:

```
python3 -c "import json;r=json.load(open('report.json'));[print(f['rule'],f['location'],f['message'],'->',f['fix_hint']) for f in r['findings'] if f['status']=='fail']"
```

## Stop conditions

Stop and report instead of looping when any of these holds:

* The same finding `id` is still present after three runs in a row. Report the finding, what you changed, and why you
  think it did not help.
* The exit code is `3`, or `result` is `error`. Fix the path or the missing input; this is not a rule failure.
* A fix needs information that is not in the profile or the files (an `Occupant` string, a level offset, a licence
  statement, the assigned entity-number start). Ask the person who gave you the profile; do not invent it.
* More than ten runs without the number of REQUIRED failures going down.
* A finding seems wrong. Say which rule and element, and what you measured. Do not work around it.

## Never do these to get a pass

* Edit a report, change a rule level, delete a check, or edit a tool to hide a finding.
* Change a value only to satisfy the checker when it makes the model less true (for example, widening a door in
  the file while the drawing says otherwise).
* Delete the element that is flagged without saying so in `notes/changes.md`.
* Run the checker on a different file than the one you deliver (rule `X-40` ties the report to the file by hash).

## Worked mini-loop

Run 1 prints a failure:

```
{ "rule": "B-42", "status": "fail", "location": {"element": "3Z2k6lcTnJFPCzw1CFlWEi"},
  "message": "doorway Entrance door is blocked at 0.6 m by Work table, 1.6 m",
  "fix_hint": "Make the opening at least 1.9 m high and remove anything (sill, bar, furniture) that crosses the doorway centre line." }
```

Fix: move the table out of the doorway and re-export. Run 2 shows `summary.requiredFailures` 0 and exit code 0. Then
rebuild the manifest (`python3 tools/build_package.py init PACKAGE_DIR package-meta.json`), run
`python3 tools/check_all.py PACKAGE_DIR --json`, and deliver.
