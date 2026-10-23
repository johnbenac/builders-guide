<!-- chunk: g5--introduction | source: 05-worked-example.md | title: Introduction | rules: - -->
<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Guide 5: Worked example

A complete, minimal delivery: one room with one door, one window, one table, one wall covering and one ceiling light, on one
level, with a finish schedule, a texture set, a library item and a package. It is small enough to read in full, and it passes
every check in guide 4 under both profiles that come with the set: `profiles/default.json` and `profiles/example-strict.json`.

The IFC file is produced by a script, not stored in this set, so that it always matches the script and the version of the IFC
library you have installed, and so that every number below can be reproduced. To build and check everything in one go:

```
pip install -r tools/requirements.txt
python3 tools/run_example.py example-out
```

This writes `example-out/example-room-1.0.0/` (the package), runs every checker on it with the default profile, builds the
manifest and ends with `build_package.py verify`. Run `python3 tools/selftest.py` to see the checker catch deliberate faults in
the same file, and `python3 tools/agent_harness.py` to see a fresh agent build and pass a delivery from the set alone.
