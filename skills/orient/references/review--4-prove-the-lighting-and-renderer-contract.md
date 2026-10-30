<!-- chunk: review--4-prove-the-lighting-and-renderer-contract | source: 09-environment-review-and-handoff.md | title: 4. Prove the lighting and renderer contract | rules: - -->
## 4. Prove the lighting and renderer contract

Document whether diffuse direct/indirect illumination is baked or evaluated at
runtime. Avoid counting both. Preserve source UVs separately from lightmap UVs;
verify geometry identity, UV coverage, overlap, receivers and gutters after optimization.

When filtering Monte Carlo noise, keep contact/direct shadow detail out of an
indirect-light smoothing operation. Filter independent atlas charts independently.
Specify linear versus display-encoded values, range/scale, texture channels and
tone mapping. Check pixel values after delivery encoding: lossy image coding can
introduce colored blocks into unrelated atlas islands. An attractive source render
does not prove an optimized map or a different renderer.

Review actual consumer views of dark rooms, bright windows, foliage backsides,
glass, metals and contact shadows. A changed sky must agree with the baked light's
direction and color convention. Record dark, noisy or implausible results as open
findings; do not declare the pipeline finished because its scripts exited successfully.
