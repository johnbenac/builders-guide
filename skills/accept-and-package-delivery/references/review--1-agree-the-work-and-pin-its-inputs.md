<!-- chunk: review--1-agree-the-work-and-pin-its-inputs | source: 09-environment-review-and-handoff.md | title: 1. Agree the work and pin its inputs | rules: - -->
## 1. Agree the work and pin its inputs

Assign one owner per editable source or shared exporter. Separate model author,
material author, consumer integration and independent review where practical.
Work on branches; do not overwrite an accepted delivery or another worker's
candidate. Independent rooms and assets can proceed in parallel. Serialize
changes to shared generators, material contracts and publication manifests.

Record the guide/profile versions and hashes, source commit, editable sources,
dependencies, exact build commands, units and coordinate transform. Distinguish
the canonical model hash from an optimized consumer model hash. A screenshot
needs the latter, its material/lightmap assets, renderer version and camera.
Use `templates/environment-handoff.template.json` for a resumable work record.
Reference the evidence manifest and frozen render-input manifest by path and hash;
they bind captures to model, pose, lightmaps, renderer modules, cameras, method and
diagnostic limits. Include those files in the portable handoff.

Deliver relative paths and immutable artifact addresses that collaborators can
access. A working-machine path or symlink alone is not a handoff. Keep rights,
font/texture dependencies, procedural seeds and storage requirements with sources.
Never include credentials or depend on a contributor's running browser session.
