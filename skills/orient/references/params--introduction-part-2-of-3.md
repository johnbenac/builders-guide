<!-- chunk: params--introduction-part-2-of-3 | source: 07-profile-parameters.md | title: Introduction (part 2 of 3) | rules: - -->
| Parameter | Meaning | default | strict | Rules |
|---|---|---|---|---|
| `frame.horizontalAxes` | which horizontal directions +X and +Y mean to this consumer (Z is up, right-handed) | `"+X forward, +Y left (right-handed with Z up)"` | `"+X forward, +Y left (right-handed with Z up)"` | B-10 |
| `frame.levelOffsetMetres` | height, in the consumer's global frame, of the file's local z = 0; declared positions in the optional extensions add it | `0.0` | `12.0` | B-12, B-92, B-133 |
| `frame.placement` | final: the consumer applies no offset or rotation to the file; the file is authored in its final placement frame | `"final"` | `"final"` | B-11 |
| `schema.allowed` | IFC schema identifiers the consumer accepts | `["IFC4"]` | `["IFC4"]` | B-01 |
| `limits.maxFileMegabytes` | hard size cap of one IFC file, in megabytes | `250` | `100` | B-05, F-50 |
| `limits.maxVertices` | hard cap on mesh vertices in one file | `10000000` | `5000000` | B-05, F-50 |
| `limits.maxTriangles` | hard cap on triangles in one file | `5000000` | `3000000` | B-05, F-50 |
| `budgets.recommendedFileMegabytes` | size above which a file is slow to load and review | `100` | `60` | B-09 |
| `budgets.recommendedTriangles` | triangle count above which load and display cost grows noticeably | `1000000` | `300000` | B-120 |
| `budgets.maxDistinctColours` | number of distinct (class, colour, opacity) combinations above which the palette is too large to manage | `50` | `30` | D-05 |
| `budgets.maxItemTriangles` | triangles of one ordinary library item | `2000` | `500` | F-51 |
| `file.singleLineEntities` | true when the consumer's reader needs every STEP entity on one line | `false` | `true` | B-08 |
| `identifiers.roomIdMaxLength` | longest allowed room identifier, in characters | `64` | `7` | B-23 |
| `identifiers.roomIdPattern` | regular expression a room identifier must match | `"^[A-Za-z0-9._-]+$"` | `"^[A-Za-z0-9-]+$"` | B-23 |
| `identifiers.entityNumberStart` | first entity number a delivery may use, so that files from several authors can be merged without clashes; null means no assigned range | `null` | `700001` | B-71 |
| `identifiers.occupants` | allowed values of the room Occupant property; null means any value | `null` | `["Example Occupant", "Agent Occupant", "Shared circulation"]` | B-24 |
| `identifiers.circulationPrefix` | text a Function value must start with for corridors and other circulation; null means no convention | `null` | `"Circulation"` | B-25 |
| `geometry.doorMinClearHeightMetres` | smallest clear height of a doorway | `2.0` | `1.9` | B-42 |
| `geometry.doorMinClearWidthMetres` | smallest clear width of a doorway | `0.8` | `0.9` | B-43 |
| `geometry.doorwayProbeHeightsMetres` | heights above the sill at which the doorway centre line must be free of solid geometry | `[0.5, 1.0, 1.8]` | `[0.6, 1.1, 1.8]` | B-42 |
| `geometry.stairRiserLimitMetres` | largest riser height of a stair | `0.19` | `0.18` | B-61 |
| `geometry.rampMaxSlope` | largest slope of a walked ramp, as rise over run (0.0833 is 1:12) | `0.0833` | `0.05` | B-64 |
| `geometry.maxCurveSegmentsPerCircle` | segments per full circle above which tessellation is wasteful | `48` | `24` | B-114 |
| `baseSurfaces` | floors the consumer supplies itself: rooms standing on them need no slab of their own | `[]` | `[]` | B-50, B-51, B-51a, B-55 |
| `buildVolume` | region all geometry must stay inside: {box:{min,max}} or {ellipse:{a,b,zmin,zmax}}, in the consumer's global frame | `null` | `{"box": {"min": [-50.0, -50.0, 0.0], "max": [50.0, 50.0, ...` | B-110 |
| `keepOut` | regions geometry must stay out of: [{id,min,max}] | `[]` | `[{"id": "example-keep-out", "min": [30.0, 30.0, 0.0], "ma...` | B-110 |
| `propertyNames` | canonical declaration property name -> the name this consumer reads; use it to rename or to point at standard property names | `{}` | `{"RoomId": "Ex_RoomId", "Occupant": "Ex_Occupant", "Funct...` | B-22, B-26, B-91 |
| `propertyValues` | canonical property -> {canonical value: consumer value} | `{}` | `{}` | - |
| `ruleLevels` | rule id -> required, recommended or off; overrides the level the rule has in rules.json | `{}` | `{"B-08": "required", "B-24": "required", "B-25": "require...` | B-26 |
| `extensions.walkability.enabled` | consumer places people or agents in rooms and walks them | `false` | `true` | - |
| `extensions.walkability.standingClearanceMetres` | free floor kept around furniture and fixed objects where a person can stand | `0.45` | `0.45` | B-33, F-32 |
| `extensions.walkability.freeCircleMetres` | diameter of a free floor circle in every enclosed room | `1.2` | `1.2` | B-34 |
| `extensions.walkability.stepHeightMetres` | height a walker steps over without noticing | `0.3` | `0.3` | B-65, F-44 |
| `extensions.walkability.nonSolidClasses` | IFC classes the consumer treats as not solid | `["IfcDoor", "IfcSpace", "IfcSpatialZone", "IfcLightFixture"]` | `["IfcDoor", "IfcSpace", "IfcSpatialZone", "IfcLightFixture"]` | B-67 |
| `extensions.luminaires.enabled` | consumer turns declared fixtures into lights | `false` | `true` | - |
| `extensions.luminaires.lensNameSuffix` | ending of the name of the emissive part | `" lens"` | `" lens"` | B-90 |
| `extensions.luminaires.requiredProperties` | properties every luminaire assembly must carry | `["LuminaireId", "LuminaireMount", "LightType", "LightEner...` | `["LuminaireId", "LuminaireMount", "LightType", "LightEner...` | B-91 |
| `extensions.luminaires.lightTypes` | allowed values of LightType | `["omni", "spot"]` | `["omni", "spot"]` | B-91 |
| `extensions.luminaires.positionToleranceMetres` | largest distance between the declared light position and the emissive part, level offset applied | `0.06` | `0.06` | B-92 |
| `extensions.luminaires.maxPerRoom` | most fixtures per room, or null | `null` | `16` | B-95 |
| `extensions.signboards.enabled` | consumer generates signs from declared boards | `false` | `true` | - |
