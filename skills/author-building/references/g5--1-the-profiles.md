<!-- chunk: g5--1-the-profiles | source: 05-worked-example.md | title: 1. The profiles | rules: - -->
## 1. The profiles

| Item | `default.json` | `example-strict.json` |
|---|---|---|
| frame offset | 0 | 12.0 m (declared positions add it) |
| room identifier | up to 64 characters | at most 7 characters, required |
| entity numbers | any | from `#700001` |
| declaration property names | as in the guides | prefixed `Ex_` (the file is renamed by `tools/map_properties.py`) |
| extensions | all off | walkability, luminaires, signboards, furniture collision on |
| limits | 250 MB, 5,000,000 triangles | 100 MB, 3,000,000 triangles |

To check the example against the strict profile, rename the properties and check with it:

```
python3 tools/map_properties.py master.ifc master-strict.ifc --mapping profiles/example-strict.json
python3 tools/check_ifc.py master-strict.ifc --profile profiles/example-strict.json
```
