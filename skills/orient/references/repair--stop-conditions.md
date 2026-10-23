<!-- chunk: repair--stop-conditions | source: REPAIR-LOOP.md | title: Stop conditions | rules: - -->
## Stop conditions

Stop and report instead of looping when any of these holds:

* The same finding `id` is still present after three runs in a row. Report the finding, what you changed, and why you
  think it did not help.
* The exit code is `3`, or `result` is `error`. Fix the path or the missing input; this is not a rule failure.
* A fix needs information that is not in the profile or the files (an `Occupant` string, a level offset, a licence
  statement, the assigned entity-number start). Ask the person who gave you the profile; do not invent it.
* More than ten runs without the number of REQUIRED failures going down.
* A finding seems wrong. Say which rule and element, and what you measured. Do not work around it.
