<!-- chunk: g1--9-names-identifiers-property-sets-and-classifica | source: 01-builders-and-architects-guide.md | title: 9. Names, identifiers, property sets and classification | rules: B-70,B-71,B-72,B-73,B-74,B-75,B-76 -->
## 9. Names, identifiers, property sets and classification

**B-70 · REQUIRED** - Give every product a unique 22-character IFC `GlobalId` that does not change between exports. `GlobalId` is the key tools use to match an element across revisions and across files.

**B-71 · RECOMMENDED** - Number your IFC entities from the start the profile assigns (`identifiers.entityNumberStart`, when set) so that files from several authors can be merged without clashes.

**B-72 · RECOMMENDED** - Write declaration properties as text, number or boolean values in `IfcPropertySingleValue` entries of an `IfcPropertySet` linked by `IfcRelDefinesByProperties` on the product itself. Many readers ignore quantity sets, enumerations, tables and properties on types.

**B-73 · RECOMMENDED** - Use one descriptive property set per topic (`Pset_Declaration_Room`, ...) and put only declaration properties in it.

**B-74 · RECOMMENDED** - If your organisation uses a classification scheme, attach it with `IfcRelAssociatesClassification`. Many consumers ignore it, so never make it the only place a meaning is written.

**B-75 · RECOMMENDED** - Keep identifiers stable across revisions: an unchanged room, door or fixture keeps its `RoomId`, `GlobalId` and declaration ids. Replace an element by giving the new one a new id and retiring the old.

**B-76 · RECOMMENDED** - Give your own identifiers dotted prefixes (`arch.entrance`, `clinic.lobby`), at most 160 characters, no control characters.
