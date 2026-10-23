<!-- chunk: sub--ingest | source: 08-submissions-and-ingest.md | title: Ingest | rules: - -->
## Ingest

`python3 tools/ingest.py deliveries/<slug> --commit <merged commit hash> --out <output folder>` is run by a maintainer or an automation, on a
checkout of the merged commit of `main` (`--require-ancestor-of origin/main` makes it refuse anything else). It never uploads and uses no
network. In order, it:

1. copies the delivery (plain files only) to a temporary folder, with a time limit (`submission.ingestMaxSeconds`) and an optional memory limit;
2. re-runs `check_submission.py` and `check_all.py` on the copy, and refuses on any REQUIRED finding;
3. splits the delivery into **components**: each item under `items/`; from the master IFC each furniture element, covering (wall, floor or
   ceiling), fixture or luminaire assembly, hardware piece, door and window; each texture set as a material set;
4. exports each geometry component as a binary glTF (GLB, units metres, Y up) and reads it back to verify it;
5. stores every file as `blobs/sha256/<hash>.<ext>`; identical bytes (for example a table in `items/` and the same table in the master, or the
   same part in two deliveries) are stored once;
6. writes `catalogue/index.json` (one entry per distinct component, with every occurrence), `catalogue/deliveries/<slug>@<commit12>.json`
   and the handoff manifest `handoff/<slug>@<commit12>.json`, shaped by `schemas/catalogue.schema.json`.

Each component carries: kind and category; dimensions and bounds; the pivot (items keep the pivot their description declares, master elements are
moved to the centre of their footprint at their lowest point); anchors; the material references that link surface colours to the finish schedule and
to the material-set components; and, per occurrence, the delivery slug, commit hash, submitter, licence, source path and IFC identifier, and its
placement in the building file. The output depends only on the delivery bytes and the commit hash, so a second run gives the same bytes. `--dry-run` shows what
would be stored and what the output folder already holds, and writes nothing.

The handoff manifest lists the blobs to publish and the components with their files, licences and submitters. Publishing them anywhere is a
separate step owned by whoever runs the catalogue; this repository defines no destination.

Limits of this version: components from the master IFC are exported as GLB only (no per-component IFC file; item components also keep their source
IFC); walls, slabs, stairs and roofs are not components, only furnishing, coverings, fixtures, hardware, doors and windows; rotations are recorded
as an angle about the vertical axis; textures are carried as material sets and are not baked into the GLB.
