<!-- chunk: g5--4-things-to-try | source: 05-worked-example.md | title: 4. Things to try | rules: - -->
## 4. Things to try

* Open `example-room-master.ifc` in any IFC viewer; it is also plain text.
* Edit `tools/make_sample.py`: rename `RoomId` to `EX-0001` and check with the strict profile (too long for 7 characters, B-23).
* Move the table to (1.4, 0.3) so that it stands in the doorway (B-42). The same fault is a case in `tools/selftest.py`.
* Remove the `IfcRelFillsElement` of the door (B-41), or change the emissive part's name to end in `glow` (B-90, strict profile).
* Change `LightPosition` height to 20 and see the mismatch (B-92, strict profile).
