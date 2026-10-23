<!-- chunk: g1--10-zones-and-reserved-volumes | source: 01-builders-and-architects-guide.md | title: 10. Zones and reserved volumes | rules: B-80,B-81,B-81a,B-82 -->
## 10. Zones and reserved volumes

**B-80 · RECOMMENDED** - Declare a volume that must stay empty or must not be solid (a sight line, a clearance, a service corridor) twice: as an `IfcSpatialZone`, and (so it can be seen) as an `IfcBuildingElementProxy` with `PredefinedType` `PROVISIONFORSPACE`. That is the standard IFC way to mark a reserved provision: consumers that understand it leave the proxy out of physical models; any other proxy is a solid thing.

**B-81 · RECOMMENDED** - Give every zone a unique identifier (`ZoneId` or, if missing, its `Name`) and its own geometry; a zone without geometry cannot be shown or selected.

**B-81a · RECOMMENDED** - Always supply `ZoneId`, plus `ZoneClass` (for example `observation-sightline`) and `Requirement` (a sentence saying what must stay clear).

**B-82 · RECOMMENDED** - Use zones to record viewing intent (a downward sight line from a mezzanine); ordinary glass cannot be one-way, and who may look is a consumer decision, not a file property.
