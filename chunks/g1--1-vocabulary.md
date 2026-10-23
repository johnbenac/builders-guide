<!-- chunk: g1--1-vocabulary | source: 01-builders-and-architects-guide.md | title: 1. Vocabulary | rules: - -->
## 1. Vocabulary

| Term | Meaning |
|---|---|
| consumer | any program or person that receives your delivery and uses it: a viewer, a simulator, a game runtime, a BIM tool, an archive |
| profile | the JSON file a consumer publishes with its parameters (limits, identifier rules, optional extensions); the default profile is `profiles/default.json` |
| master file | the single coordinated IFC file for one placement area |
| level | one floor of a building: an `IfcBuildingStorey` |
| room | a named area with a floor, modelled as an `IfcSpace` (the IFC entity name; here it always means "room or zone") |
| zone | a named volume that is data only: an `IfcSpatialZone` |
| declaration property | a named property this set asks you to write because consumers read it (for example `RoomId`); a profile can rename them |
| extension | an optional group of rules a profile switches on when its consumer needs it: walkability, luminaires, signboards, furniture collision |
