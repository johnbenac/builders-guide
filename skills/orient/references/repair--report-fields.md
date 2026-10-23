<!-- chunk: repair--report-fields | source: REPAIR-LOOP.md | title: Report fields | rules: - -->
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
