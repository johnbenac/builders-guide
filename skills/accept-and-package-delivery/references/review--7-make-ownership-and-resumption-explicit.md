<!-- chunk: review--7-make-ownership-and-resumption-explicit | source: 09-environment-review-and-handoff.md | title: 7. Make ownership and resumption explicit | rules: - -->
## 7. Make ownership and resumption explicit

A handoff records who owns each mutable file, the input digest, work state,
last verified result and the next dependency. A claim reserves editing, not
acceptance. Before taking over an apparently stale claim, contact its owner or
verify that its job has stopped; reconcile shared edits explicitly. Do not
infer completion from silence or overwrite a running worker's output.

Separate portable relative paths from optional machine-local working paths.
Record host, process/job handle and cleanup responsibility for active work;
never include credentials. Rehearse from a fresh extraction, including a path
with spaces. State separately whether dependencies were freshly installed and
whether another machine reproduced it. A same-host replay proves neither.
