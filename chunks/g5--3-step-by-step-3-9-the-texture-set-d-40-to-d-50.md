<!-- chunk: g5--3-step-by-step-3-9-the-texture-set-d-40-to-d-50 | source: 05-worked-example.md | title: 3. Step by step: 3.9 The texture set (D-40 to D-50) | rules: - -->
### 3.9 The texture set (D-40 to D-50)

`finishes/textures/plaster_example/` has `albedo.png`, `normal.png`, `orm.png` and `set.json` (1024 by 1024 pixels, 2 m per tile, so
512 pixels per metre; `tintMode` `multiply`). It is made by `tools/make_sample_texture_set.py` from seamless noise with a fixed seed.
`check_texture_set.py --preview wrap.png` writes the three-by-three arrangement so you can see that the edges do not show.
