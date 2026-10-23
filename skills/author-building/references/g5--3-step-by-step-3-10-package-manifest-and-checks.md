<!-- chunk: g5--3-step-by-step-3-10-package-manifest-and-checks | source: 05-worked-example.md | title: 3. Step by step: 3.10 Package, manifest and checks (guide 4) | rules: - -->
### 3.10 Package, manifest and checks (guide 4)

`run_example.py` writes the check reports into `reports/`, writes `package-meta.json`, and runs `build_package.py init` then
`verify`. The final package listing:

```
example-room-1.0.0/
  manifest.json   SHA256SUMS.txt
  ifc/example-room-master.ifc
  tables/{rooms.csv,building.json}
  finishes/{finish-schedule.json,library.json,SOURCES.csv}
  finishes/textures/plaster_example/{albedo.png,normal.png,orm.png,set.json}
  items/table.work.1600/{table.work.1600.ifc,table.work.1600.item.json}
  reports/{check_ifc.json,check_texture_set.json,check_item-table.work.1600.json}
  notes/changes.md
```

Expected output of the IFC check:

```
result: PASS (0 REQUIRED failure(s), 0 RECOMMENDED warning(s)); 1 levels, 1 rooms, 1 doors,
1 windows, 1 luminaires, 216 triangles, 136 vertices, 1 furniture, 9 finishKeys
```
