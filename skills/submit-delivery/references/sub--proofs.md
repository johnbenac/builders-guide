<!-- chunk: sub--proofs | source: 08-submissions-and-ingest.md | title: Proofs | rules: - -->
## Proofs

Every submitted delivery carries **proofs**: models and pictures that anyone can look at without a modelling program, and rebuild to see that
they are honest. `python3 tools/build_proofs.py deliveries/<slug>` makes all of them from the delivered files, in three steps, and writes
`proofs/manifest.json` (`schemas/proofs.schema.json`, format `proofs/1`):

1. **Export** (`tools/export_glb.py`): `proofs/glb/model.glb` (the whole master IFC as a scene graph: `model` > `level:<name>` >
   `<kind>:<name>#<GlobalId>`), `proofs/glb/components/*.glb` (one per item and per furniture element, covering, fixture or luminaire
   assembly, hardware piece, door and window, exactly the GLB `ingest.py` stores for it) and `proofs/glb/materials/*.glb` (a 2 x 2 swatch of each
   texture set with its maps embedded). Units are metres and the axes are Y up: an IFC point (x, y, z) becomes (x, z, -y). Colours are PBR
   metallic-roughness materials. The files are deterministic and hold no path, time, user or host.
2. **Validate** (`tools/validate_glb.py`): structure (container, indices, accessors, images, materials, scene graph, nothing unused, no URI),
   conventions (units and axis note, generator, size, unit-length normals, tangents with a normal map, node names), the profile's budgets, and
   with `--ifc` each product's bounding box against the IFC file. The Khronos glTF Validator (Apache-2.0, pinned in
   `tools/khronos/package-lock.json`, `npm ci --prefix tools/khronos`) is run as well when it is installed. The report is
   `proofs/reports/glb-validation.json` (`check-report/1`, rule X-80).
3. **Render** (`tools/render.py`), from the GLB files only: a plan for each level (cut at 1.2 m), four interior views for each room kind
   present (kind = the room's `Function` property; the first two rooms of a kind by identifier), four exterior views, and a contact sheet of
   eight turntable frames for every component (four fixed frames for a texture swatch).

The renderer is a software rasteriser in numpy (about 400 lines): no graphics card, display, browser or system library, so the same GLB gives
the same picture on a laptop and on a hosted runner. It draws flat-shaded triangles with a z-buffer, 2 x 2 supersampled, with base colours and
the base colour texture; it does not draw normal maps, metal, roughness, shadows or reflections. The lighting, background, camera and sizes are
fixed conventions, recorded for every picture (`tools/render.py` states them). A headless browser with a bundled viewer library, or Blender, would draw
nicer pictures, but they depend on a graphics stack that differs between machines, so the same file would not give the same picture; the
choice favours reproducibility over beauty. (Tried while choosing: headless Chromium with software WebGL runs here and repeats itself on one machine, but needs a browser, a
vendored viewer library of some hundreds of kilobytes, and gives pixels that depend on the browser and graphics-layer build; Blender is optional
high-quality software that is far larger than this repository and, with a graphics card, differs from machine to machine.) The manifest records, for every GLB, its SHA-256, size and source IFC hash, and for every picture
its path, SHA-256, pixel size, camera, light, the hash of the GLB it was made from and the tool and version.

`python3 tools/check_proofs.py deliveries/<slug>` checks the manifest against the files (X-79), the GLB files against their sources and the
validation report (X-81, X-80), the coverage of the pictures (X-82), the traceability of each picture to a delivered GLB (X-83), the size limits
(X-84) and the metadata of every image and GLB (X-85); with `--reproduce` it also rebuilds the GLB files, compares the bytes, re-renders every
picture from the delivered GLB and compares it within `proofs.renderTolerance` (X-86). Where the toolchain is not available it says so (an
`info` finding) and skips; it never reports a skipped check as passed. Make the proofs again after any change to an IFC file, item or texture set.
