<!-- chunk: g3--2-classes-and-categories | source: 03-furniture-and-fixtures-guide.md | title: 2. Classes and categories | rules: F-01,F-02,F-03 -->
## 2. Classes and categories

**F-01 · REQUIRED** - Use these classes for items, because consumers and tools are written for them, and make the description's class agree with the model.

| Item kind | IFC class | Typical consumer treatment |
|---|---|---|
| movable furniture (tables, chairs, benches, beds, shelves, sofas) | `IfcFurnishingElement` | simple shape or box; the default choice |
| fixed equipment, built-in units, counters, anything where the exact solid shape matters | `IfcBuildingElementProxy` (`PredefinedType` `USERDEFINED`, `ObjectType` set) | exact triangle mesh |
| light fixtures | `IfcElementAssembly` of two `IfcLightFixture` parts | see guide 1, section 11 |
| signs and boards | `IfcElementAssembly` | see guide 1, section 12 |
| rails and guards | `IfcRailing` | cheap geometry (guide 1, B-66) |
| lifts | `IfcTransportElement` (`ELEVATOR`) | usually static (guide 1, B-63) |

Other classes are drawn but get no special treatment; ask before using them for items.

**F-02 · RECOMMENDED** - Set `ObjectType` to a category word from this list so that reports and schedules can group items: `table`, `desk`, `seat`, `bench`, `sofa`, `bed`, `shelf`, `cabinet`, `counter`, `partition`, `planter`, `equipment`, `appliance`, `lamp`, `sign`, `accent`, `other`.

**F-03 · RECOMMENDED** - Add a property set `Pset_Declaration_Item` with text properties `ItemId` (the library id, section 3), `ItemVersion` (SemVer), `Role` (what the item is for, for example `work table`), and optionally `Occupant` and `PlanningStatus`.
