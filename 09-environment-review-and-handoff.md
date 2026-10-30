<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Environment review and asynchronous handoff

This procedure supplements guides 1–4. It adds review guidance, not new default
rule levels. The consumer's profile supplies tolerances, clearance, camera,
device and performance targets. A valid file can still depict a poor environment.

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

## 2. Check construction and usable space before multiplying media

Inventory every authored room, exterior and connection. Review a complete set
of directions and upward/downward joins, then relevant closeups. A few attractive
hero views do not prove room coverage. List places not inspected and why.

Inspect openings, wall/roof/bay joins, thresholds, chimney bores and flashing,
hardware attachment, furniture clearances, support contacts and actual object
orientation. Check props against the real support surface, not an assumed floor
height. Model masonry bonds and corner returns when joints must align.

Verify the requested open-door state against actual fixed surfaces and other
open leaves. “Open” is not synonymous with “passable.” Do not hide a blocking
leaf, enlarge a clearance result, or rotate a leaf into a wall to obtain a pass.
Preserve the neutral rig and record hinge, parts and applied pose exactly once.
Test intermediate states as well as endpoints, including linked folding leaves.
Retain all actual surface-contact witnesses. Labels such as hinge-region or
floor-level describe a contact; they do not establish that it is harmless.
Inspect the contacted object and the profile tolerance before accepting it.

Check functional fixture geometry: a basin needs an open cavity, a credible rim
and a drain; a painted circular cap is not a bowl. Inspect supporting counters,
trays and taps for intersections. Keep already-correct fixtures unchanged.

Use actual finished-floor geometry for steps, decks and ramps. Semantic level
labels and large furniture bounding boxes can misrepresent walkable space.
Evaluate the consumer's body clearance and all required connections; compute
connectivity again after stair/threshold repairs. A room viewpoint should lie on
an accessible component, not a comfortable-looking isolated patch behind furniture.
Separate photographic compositions from natural standing/entry viewpoints.
Verify the actual projection matrix, sensor convention and aspect ratio. A nominal
lens label is insufficient if the consumer ignores it or applies a default field
of view; qualify affected historical captures rather than silently relabeling them.

## 3. Review material authoring and exported appearance separately

Name the intended surface: paint, wood species, metal/coating, plaster, glass,
fabric, stone, foliage. A solid painted finish is often correct; do not substitute
a generic timber or noise texture merely because the exporter has one available.

Check UV orientation, real scale, repetition and seams at corners and close range.
Inspect color, normal, roughness, metallic, emission and optical properties after
export and import into the intended consumer. Retain material identity through
batching. Inspect winding and authored normals on both sides of foliage. For
closed shells, check outward orientation as well as surface positions; preserve
intentional single-sided geometry under the profile's sidedness convention.
Use explicit surface intent when several surfaces share a palette color: soil
and stained timber must not acquire the same finish through color matching.
Texture-cache keys must include settings that change the resulting material.

Alpha coverage alone does not establish believable clear glass. Preserve the
source's intended transmission, index of refraction and roughness using supported
properties; keep mirror and painted/opaque surfaces distinct. Record unsupported
features. Do not silently replace materials by name in a proof renderer: that can
make a broken export appear correct. Label diagnostic fill lights and substitutions;
they cannot prove the unmodified consumer's appearance.

## 4. Prove the lighting and renderer contract

Document whether diffuse direct/indirect illumination is baked or evaluated at
runtime. Avoid counting both. Preserve source UVs separately from lightmap UVs;
verify geometry identity, UV coverage, overlap, receivers and gutters after optimization.
Positive UV area does not guarantee lighting samples. Check actual texel-center
support at the delivered atlas resolution, including quantized consumer UVs and
bilinear filter footprints. Gutters cannot restore illumination that was never
sampled. Group charts by UV and physical edge continuity; object/material names
alone neither establish continuity nor require a seam. Record unsupported faces
and memory/transfer costs before selecting a denser layout or additional atlases.

When filtering Monte Carlo noise, keep contact/direct shadow detail out of an
indirect-light smoothing operation. Filter independent atlas charts independently.
Specify linear versus display-encoded values, range/scale, texture channels and
tone mapping. Check pixel values after delivery encoding: lossy image coding can
introduce colored blocks into unrelated atlas islands. An attractive source render
does not prove an optimized map or a different renderer. Isolate albedo, direct
and indirect illumination before changing textures or adding fill to conceal a
lighting defect. Record sampling, path-depth, glossy-blur and clamping settings:
noise controls can change transmitted energy, and more samples alone may not
remove that bias. Keep raw passes and compare bounded transport fixtures against
an appropriate physical reference; record convergence limits explicitly.

Review actual consumer views of dark rooms, bright windows, foliage backsides,
glass, metals and contact shadows. A changed sky must agree with the baked light's
direction and color convention. Record dark, noisy or implausible results as open
findings; do not declare the pipeline finished because its scripts exited successfully.

## 5. Package evidence that another contributor can continue

For each finding record severity, affected objects/rooms, observation, artifact
hashes, correction owner, attempted fix and the matching verification view. Keep
baseline and candidate evidence separate. A changed artifact invalidates its old
acceptance; record a superseding decision rather than editing away adverse evidence.

| Change | Evidence to revisit |
|---|---|
| Geometry or pose | Collision/support, connectivity, room stops, UVs, bake, media and consumer integration |
| Materials or source UVs | Export/import parity, relevant bake contributions, optical closeups and media |
| Renderer, sky or lighting | Matched views, affected media and device measurements |
| Encoding/optimization | Decoded pixels/surfaces, attribute retention and consumer views |
| Labels or publication only | Affected links, accessibility, asset integrity and deployed behavior |

Reuse a prior geometry/navigation result for a material-only revision only when
an explicit equivalence check proves unchanged relevant geometry and poses. A
matching vertex count is insufficient; changed triangle diagonals can matter.

Record reviewer independence and limits. Schema validation, image existence,
reproducibility and visual acceptance are separate results. A diagnostic render,
software renderer or emulated phone must not be represented as a physical-device test.
Measure actual transfer, first usable frame, frame times and repeated-entry resource
cleanup. Optimize from evidence without hiding quality loss or inventing a universal limit.

## 6. Resume and improve

The receiving contributor verifies artifact hashes, reads open findings and runs
the recorded next command. Record the output revision, decisions and remaining
work in the handoff; attach readable contact sheets and exact evidence files.
Release owned processes and scratch storage without deleting editable masters.
Do not claim an old job is running without checking its real handle.

When a defect escapes the process, add its general cause, a reproducible example
and a source/export/review check to the appropriate guide or tool. Fix the shared
recipe as well as the particular asset. Acceptance remains the receiving party's
explicit, revision-bound decision under guide 4.

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
