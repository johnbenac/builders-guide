<!-- chunk: g4--8-submitting-a-delivery-as-a-pull-request-8-1-pr | source: 04-delivery-and-acceptance-guide.md | title: 8. Submitting a delivery as a pull request: 8.1 Proofs: models and pictures that anyone can reproduce | rules: X-79,X-80,X-81,X-82,X-83,X-84,X-85,X-86 -->
### 8.1 Proofs: models and pictures that anyone can reproduce

A reviewer should not have to open a modelling program to see what a delivery is. Every submitted delivery therefore carries **proofs** in
`proofs/`: binary glTF (GLB) exports of the whole model and of every component, a validation report for those exports, and a standard set of
rendered pictures, all tied together by `proofs/manifest.json` (`schemas/proofs.schema.json`, format `proofs/1`). One command makes them:
`python3 tools/build_proofs.py deliveries/<slug>` (export with `tools/export_glb.py`, validation with `tools/validate_glb.py`, pictures with
`tools/render.py`); `python3 tools/check_proofs.py deliveries/<slug> --reproduce` checks them and rebuilds them to compare. Everything runs
without a graphics card or a display, so the same files come out on a laptop and on a build server. The limits are the `proofs` group of the
profile (`07-profile-parameters.md`); the numbers below are the defaults.

The GLB files use metres and Y up: a point of the IFC frame (Z up) becomes `(x, y, z) -> (x, z, -y)`. Colours become PBR metallic-roughness
materials; a texture set becomes a swatch with its maps embedded. The pictures use fixed lighting and a fixed background and are always made
from the delivered GLB files, never from anything else: a plan per level (cut at 1.2 m above the floor), four interior views for each room kind
that is present, four exterior views, and for every component a contact sheet of turntable frames (a swatch view for a texture set).

**X-79 · REQUIRED** - Put a proof manifest at `proofs/manifest.json` (format `proofs/1`) that lists every GLB, the GLB validation report and every render with its SHA-256, size and the tool and version that made it, and put nothing else in `proofs/`. A reviewer, a catalogue and the intake tool need one file that says exactly which models and pictures belong to which source, and a way to see that none was changed afterwards.

**X-80 · REQUIRED** - Make every delivered GLB a valid binary glTF 2 file in metres with Y up, with no external reference, no unused buffer, image or material, finite and unit-length normals, tangents where a normal map is used, named scene-graph nodes, and the node, triangle and texture limits of the profile. A GLB that is malformed, in another unit or axis, or that points outside itself shows a consumer a different building than the IFC file does, or crashes it.

**X-81 · REQUIRED** - Deliver a GLB of the whole master model and one of every item, covering, fixture, hardware piece, door, window and texture set, each made from the delivered IFC files (their SHA-256 is recorded), together with a validation report that passes and names every GLB by its SHA-256. The GLB files are what the pictures are made from and what a consumer without an IFC reader opens, so they must correspond to the delivered source and be known to be valid.

**X-82 · REQUIRED** - Include renders that cover every level (a plan), every room kind present (the profile's number of interior views), the outside of the building, and every item, covering, fixture, hardware piece, door, window and texture set (a contact sheet). A picture set that leaves out a level, a kind of room or a component lets a defect there go unseen.

**X-83 · REQUIRED** - Make every render from a GLB of the delivery and record in the manifest the SHA-256 of that GLB, of the picture itself, its pixel size, the camera and the lighting; each recorded GLB hash must be the hash of the delivered GLB file. A picture that cannot be traced to the exact model it shows proves nothing about it.

**X-84 · REQUIRED** - Keep every render within the profile's pixel and file-size limits (`proofs.minRenderWidth`, `proofs.maxRenderPixels`, `proofs.maxRenderBytes`) and the whole `proofs/` folder within `proofs.maxProofBytes`. Pictures are for looking at on shared machines; a very large one costs every reviewer, and a tiny one shows nothing.

**X-85 · REQUIRED** - Keep personal data and local paths out of images and GLB files: renders hold only the image chunks the profile allows, no image holds EXIF, XMP, a colour profile with text or text that names a person, a folder, a host or an address, and no GLB holds a path, an address, an e-mail address or a generator other than the set's. A file that records who made it, where, or on which machine leaks that to everyone who receives the delivery.

**X-86 · REQUIRED** - Make the proofs reproducible: rebuilding the GLB files from the delivered IFC files must give the same bytes, and re-rendering the delivered GLB files must give pictures that differ from the delivered ones by no more than `proofs.renderTolerance`; where the toolchain is not available the check says so and is skipped, not passed. Proofs that cannot be reproduced cannot be trusted, and a rebuild is the cheapest way to see that the pictures do show the model.

Acceptance of a submission is a merge to `main`; see `08-submissions-and-ingest.md` for what happens next. The checks cannot judge quality,
ownership or taste: a person reviews those, and may decline a delivery that passes every check.
