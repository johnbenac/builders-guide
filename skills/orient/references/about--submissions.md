<!-- chunk: about--submissions | source: ABOUT.md | title: Submissions | rules: - -->
## Submissions

The repository that holds this set also takes outside **deliveries** (buildings, interiors, furniture, materials, fixtures, hardware). A
contributor forks the repository, builds the delivery in a branch of the fork under `deliveries/<slug>/`, and opens a pull request against
`main`. A workflow checks it; a maintainer reviews it; a merge to `main` is the acceptance. A separate tool, `tools/ingest.py`, then turns a merged
delivery into content-addressed component assets and a neutral catalogue, without uploading anything. Deliveries are not part of the guide set
and are left out of the hand-over files. See `08-submissions-and-ingest.md`.

Every delivery also carries **proofs**: binary glTF (GLB) exports of the model and its components, a validation report, and a standard set of
rendered pictures (a plan per level, interior and exterior views, a contact sheet per component), all drawn headlessly and reproducibly from the GLB
files and tied together by a manifest of hashes, so that a reviewer or a catalogue can see the work without opening an IFC program.
