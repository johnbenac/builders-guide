<!-- chunk: repair--never-do-these-to-get-a-pass | source: REPAIR-LOOP.md | title: Never do these to get a pass | rules: - -->
## Never do these to get a pass

* Edit a report, change a rule level, delete a check, or edit a tool to hide a finding.
* Change a value only to satisfy the checker when it makes the model less true (for example, widening a door in
  the file while the drawing says otherwise).
* Delete the element that is flagged without saying so in `notes/changes.md`.
* Run the checker on a different file than the one you deliver (rule `X-40` ties the report to the file by hash).
