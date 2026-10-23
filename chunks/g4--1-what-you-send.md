<!-- chunk: g4--1-what-you-send | source: 04-delivery-and-acceptance-guide.md | title: 1. What you send | rules: X-01,X-02 -->
## 1. What you send

A delivery is one folder (and a zip of it) with these parts. Send only the parts your assignment needs.

```
example-room-1.0.0/
  manifest.json               what is in the package, with hashes (section 3)
  SHA256SUMS.txt              the same hashes in the plain checksum-file form
  ifc/
    example-room-master.ifc   the one coordinated master IFC file (buildings)
    alternates/               optional per-building files (not the master)
  tables/
    rooms.csv                 room table: ids, names, occupants, kinds (section 6)
    building.json             optional machine-readable building summary
  finishes/
    finish-schedule.json      what each colour and each floor means (guide 2)
    library.json              optional list of texture sets and the schedule
    SOURCES.csv               source and licence of every texture set
    textures/<set>/           albedo.png, normal.png, orm.png, set.json
  items/<itemId>/             <itemId>.ifc, <itemId>.item.json, optional preview.png (guide 3)
  reports/                    the checker reports (section 5)
  notes/
    changes.md                what changed since the previous version
    open-points.md            anything you could not settle
```

**X-01 · REQUIRED** - Use this layout. Tools and reviewers find things by these folder names and roles. A building delivery has exactly one file under `ifc/` (not in `alternates/`).

**X-02 · RECOMMENDED** - Use lower-case ASCII file names without blanks, forward slashes in every path, and keep paths under 200 characters. Put nothing in the package that is not listed in the manifest.
