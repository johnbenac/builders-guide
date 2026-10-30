<!-- chunk: review--4-prove-the-lighting-and-renderer-contract | source: 09-environment-review-and-handoff.md | title: 4. Prove the lighting and renderer contract | rules: - -->
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
