<!-- chunk: g5--6-larger-examples | source: 05-worked-example.md | title: 6. Larger examples | rules: - -->
## 6. Larger examples

`python3 tools/make_fixtures.py out/` builds three more buildings with the authoring kit `tools/ifc_author.py`. Each passes `check_ifc.py` without warnings; `tools/test_fixtures.py` also runs them through the terrain tools and breaks each of the rules they exercise.

| Fixture | What it shows |
|---|---|
| `tray-house` | two levels of cantilevered trays over a watercourse: stacked slabs, open-air terraces (B-143), a stair through a slab well sized for head-room (B-61, B-53), a stone core, parapets |
| `hillside-block` | a block stepped up a steep slope and turned 30 degrees from east: two ground-contact levels (B-141), footings and a retaining wall (B-142), a gable roof of sloped slabs (B-144), a stair that arrives on a roof terrace |
| `courtyard` | four wings round an open courtyard on one level: battered outer walls (B-144), flat roofs with a courtyard opening, parapets, open-air circulation reached by doors (B-47) |

To see a building, run `python3 tools/preview.py MASTER.ifc OUT_DIR`: one plan per level and an isometric view.
