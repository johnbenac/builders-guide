<!-- chunk: repair--worked-mini-loop | source: REPAIR-LOOP.md | title: Worked mini-loop | rules: - -->
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
