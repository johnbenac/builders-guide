<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Profile parameters

Every value that depends on a consumer is a parameter of a profile (`profiles/profile.schema.json`). This table is generated from the schema and the two profiles that come with the set. `default` is `profiles/default.json`; `strict` is the illustrative consumer profile `profiles/example-strict.json`. A consumer publishes its own profile in the same shape; a parameter it omits takes the default.

| Parameter | Meaning | default | strict | Rules |
|---|---|---|---|---|
| `frame.horizontalAxes` | which horizontal directions +X and +Y mean to this consumer (Z is up, right-handed) | `"+X forward, +Y left (right-handed with Z up)"` | `"+X forward, +Y left (right-handed with Z up)"` | B-10 |
| `frame.levelOffsetMetres` | height, in the consumer's global frame, of the file's local z = 0; declared positions in the optional extensions add it | `0.0` | `12.0` | B-12, B-92, B-133 |
| `frame.placement` | final: the consumer applies no offset or rotation to the file; the file is authored in its final placement frame | `"final"` | `"final"` | B-11 |
| `schema.allowed` | IFC schema identifiers the consumer accepts | `["IFC4"]` | `["IFC4"]` | B-01 |
| `limits.maxFileMegabytes` | hard size cap of one IFC file, in megabytes | `250` | `100` | B-05, F-50 |
| `limits.maxVertices` | hard cap on mesh vertices in one file | `10000000` | `5000000` | B-05, F-50 |
| `limits.maxTriangles` | hard cap on triangles in one file | `5000000` | `3000000` | B-05, F-50, X-80 |
| `budgets.recommendedFileMegabytes` | size above which a file is slow to load and review | `100` | `60` | B-09 |
| `budgets.recommendedTriangles` | triangle count above which load and display cost grows noticeably | `1000000` | `300000` | B-120, X-80 |
| `budgets.maxDistinctColours` | number of distinct (class, colour, opacity) combinations above which the palette is too large to manage | `50` | `30` | D-05 |
| `budgets.maxItemTriangles` | triangles of one ordinary library item | `2000` | `500` | F-51, X-80 |
| `file.singleLineEntities` | true when the consumer's reader needs every STEP entity on one line | `false` | `true` | B-08 |
| `identifiers.roomIdMaxLength` | longest allowed room identifier, in characters | `64` | `7` | B-23 |
| `identifiers.roomIdPattern` | regular expression a room identifier must match | `"^[A-Za-z0-9._-]+$"` | `"^[A-Za-z0-9-]+$"` | B-23 |
| `identifiers.entityNumberStart` | first entity number a delivery may use, so that files from several authors can be merged without clashes; null means no assigned range | `null` | `700001` | B-71 |
| `identifiers.occupants` | allowed values of the room Occupant property; null means any value | `null` | `["Example Occupant", "Agent Occupant", "Shared circulation"]` | B-24 |
| `identifiers.circulationPrefix` | text a Function value must start with for corridors and other circulation; null means no convention | `null` | `"Circulation"` | B-25, B-47 |
| `geometry.doorMinClearHeightMetres` | smallest clear height of a doorway | `2.0` | `1.9` | B-42 |
| `geometry.doorMinClearWidthMetres` | smallest clear width of a doorway | `0.8` | `0.9` | B-43 |
| `geometry.doorwayProbeHeightsMetres` | heights above the sill at which the doorway centre line must be free of solid geometry | `[0.5, 1.0, 1.8]` | `[0.6, 1.1, 1.8]` | B-42 |
| `geometry.stairRiserLimitMetres` | largest riser height of a stair | `0.19` | `0.18` | B-61 |
| `geometry.rampMaxSlope` | largest slope of a walked ramp, as rise over run (0.0833 is 1:12) | `0.0833` | `0.05` | B-64 |
| `geometry.maxCurveSegmentsPerCircle` | segments per full circle above which tessellation is wasteful | `48` | `24` | B-114 |
| `geometry.stairHeadroomMetres` | clear height required above every stair tread | `2.0` | `2.0` | B-61 |
| `geometry.roomOverlapToleranceMetres` | largest thickness by which two rooms on one level may overlap (a wall) | `0.5` | `0.5` | B-30 |
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
| `extensions.signboards.kinds` | allowed values of SignboardKind | `["entrance_board", "stop_board"]` | `["entrance_board", "stop_board"]` | B-100 |
| `extensions.signboards.requiredProperties` | properties every board must carry | `["SignboardId", "SignboardKind", "SignboardText", "Signbo...` | `["SignboardId", "SignboardKind", "SignboardText", "Signbo...` | B-100 |
| `extensions.signboards.displayPixelsPerRadian` | pixels per radian of the display, used for legibility | `1000` | `1090` | B-102 |
| `extensions.signboards.minCapitalPixels` | smallest capital height in pixels for primary, secondary and tertiary text | `{"primary": 16, "secondary": 12, "tertiary": 9}` | `{"primary": 16, "secondary": 12, "tertiary": 9}` | B-102 |
| `extensions.signboards.readingDistanceMetres` | smallest and largest accepted reading distance | `[5, 18]` | `[5, 18]` | B-102 |
| `extensions.furnitureCollision.enabled` | consumer approximates furniture with a simple collider | `false` | `true` | - |
| `extensions.furnitureCollision.mode` | box: one axis-aligned box per furniture element; mesh: exact triangles | `"box"` | `"box"` | F-40 |
| `extensions.terrain.enabled` | consumer supplies terrain from its own source and wants a derived, read-only terrain patch in the file | `false` | `false` | - |
| `extensions.terrain.crsName` | name of the consumer's site coordinate reference system, written as the IfcProjectedCRS name; it need not be a registry code; null accepts any non-empty name | `null` | `null` | B-133 |
| `extensions.terrain.patchFormat` | form of the height patch the consumer's terrain source delivers | `"geotiff-float32-metres"` | `"geotiff-float32-metres"` | - |
| `extensions.terrain.maxErrorBoundMetres` | largest vertical difference allowed between the terrain triangles and the source samples | `0.05` | `0.05` | B-137 |
| `extensions.terrain.footprintMarginMetres` | margin by which the terrain patch must extend beyond the building footprint in plan | `10.0` | `10.0` | B-132 |
| `extensions.terrain.clearingMarginMetres` | margin round the footprint in which the terrain source clears vegetation | `2.0` | `2.0` | - |
| `extensions.terrain.grading` | grading rule sent to the terrain source: maxCutFillSlope is the steepest cut or fill slope as horizontal:vertical text, for example 1:2 | `{"maxCutFillSlope": "1:2"}` | `{"maxCutFillSlope": "1:2"}` | - |
| `extensions.terrain.seaLevelMetres` | height of sea level in the consumer's vertical datum; terrain below it is seabed | `0.0` | `0.0` | B-135 |
| `extensions.terrain.floatToleranceMetres` | how far the lowest finished floor may stand above the terrain at every footprint point before the building counts as floating | `0.5` | `0.5` | B-136 |
| `extensions.terrain.buryToleranceMetres` | how far the lowest finished floor may stand below the terrain at every footprint point before the building counts as buried | `0.5` | `0.5` | B-136 |
| `extensions.terrain.siteElevationToleranceMetres` | largest difference between IfcSite.RefElevation and the terrain height at the building origin | `0.1` | `0.1` | B-134 |
| `extensions.terrain.maxTriangles` | most triangles in the terrain element | `200000` | `200000` | B-138 |
| `extensions.terrain.maxPatchSamples` | most samples read from one height patch; a larger patch is refused before it is loaded | `25000000` | `25000000` | - |
| `textures.sizesPixels` | allowed texture map sizes in pixels (square) | `[512, 1024, 2048]` | `[1024]` | D-44, X-80 |
| `textures.densityPixelsPerMetre` | smallest and largest texel density | `[250, 2500]` | `[340, 2050]` | D-45 |
| `textures.maps` | map file names a set must contain, without extension | `["albedo", "normal", "orm"]` | `["albedo", "normal", "orm"]` | D-40, D-41 |
| `textures.normalConvention` | +Y: green channel points up (OpenGL style); -Y: green points down (DirectX style) | `"+Y"` | `"+Y"` | D-41 |
| `textures.tintModes` | allowed values of tintMode in set.json | `["multiply", "authored"]` | `["multiply", "authored"]` | D-47 |
| `package.maxPackageMegabytes` | upload size cap of a whole package, or null | `null` | `500` | X-14 |
| `package.requireProvenance` | every asset needs a provenance entry | `true` | `true` | X-20 |
| `package.requireLicence` | every asset and the package need a licence | `true` | `true` | X-21 |
| `submission.maxFiles` | most files in one delivery folder (600 since 2.3.0, because proofs add a GLB and a contact sheet for every component) | `600` | `null` | X-73 |
| `submission.maxFileBytes` | largest single file in a delivery, in bytes | `26214400` | `null` | X-73, X-80 |
| `submission.maxDeliveryBytes` | largest total size of a delivery folder, in bytes | `104857600` | `null` | X-73 |
| `submission.maxPathLength` | longest relative path inside a delivery, in characters | `200` | `null` | X-74 |
| `submission.allowedExtensions` | file name endings allowed in a delivery, lower case, without the dot; anything else (programs, scripts, archives) is refused | `["ifc", "glb", "png", "jpg", "json", "md", "csv", "txt"]` | `null` | X-72 |
| `submission.allowedLicences` | licence identifiers a submitter may offer the delivery under | `["CC-BY-4.0", "CC0-1.0"]` | `null` | X-71 |
| `submission.ingestMaxComponents` | most component assets one delivery may be split into by tools/ingest.py | `500` | `null` | - |
| `submission.ingestMaxSeconds` | time limit of one tools/ingest.py run, in seconds | `300` | `null` | - |
| `submission.maxImagePixels` | most pixels (width times height) of one PNG or JPEG image in a delivery; protects reviewers and ingest from decompression bombs | `67108864` | `null` | X-77 |
| `proofs.maxGlbNodes` | most scene-graph nodes in one GLB | `20000` | `null` | X-80 |
| `proofs.maxExtentMetres` | largest size of a GLB along any axis, in metres; a bigger model has probably been exported in the wrong unit | `5000` | `null` | X-80 |
| `proofs.interiorViewsPerRoom` | interior views rendered for each room that is shown (camera at a standard eye height, derived from the room's footprint) | `4` | `null` | X-82 |
| `proofs.maxRoomsPerKind` | most rooms of one kind (the room's Function property) that are rendered; the first rooms by identifier | `2` | `null` | - |
| `proofs.exteriorViews` | exterior views of the whole building, evenly spaced around it | `4` | `null` | X-82 |
| `proofs.turntableFrames` | frames of the turntable contact sheet of a component (material sets use a fixed set of four) | `8` | `null` | - |
| `proofs.minRenderWidth` | smallest width of a render, in pixels | `256` | `null` | X-84 |
| `proofs.maxRenderPixels` | most pixels (width times height) of one render | `2097152` | `null` | X-84 |
| `proofs.maxRenderBytes` | largest file size of one render, in bytes | `3145728` | `null` | X-84 |
| `proofs.maxProofBytes` | largest total size of the proofs/ folder, in bytes | `67108864` | `null` | X-84 |
| `proofs.glbVolumes` | what the GLB export does with zones (IfcSpatialZone) and reservation volumes (IfcBuildingElementProxy of type PROVISIONFORSPACE): mesh exports them like any product; exclude leaves them out, lists them in extras.excluded of the whole-model GLB, and the validator accepts their missing nodes only through that list | `"mesh"` | `null` | X-80 |
| `proofs.glbPivots` | where each product of the whole-model GLB has its origin: world bakes every vertex into world coordinates (every origin is the model origin); placement uses the origin of the product's IFC placement, so the node carries the placement and identical shapes share one mesh; footprint uses the centre of the footprint at the lowest point | `"world"` | `null` | X-80 |
| `proofs.glbIndexed` | share vertices that agree in position and normal in the whole-model GLB (indexed primitives) | `false` | `null` | X-80 |
| `proofs.renderTolerance.meanAbsLevels` |  | `0.5` | `null` | - |
| `proofs.renderTolerance.differingFraction` |  | `0.001` | `null` | - |
| `proofs.renderTolerance.differenceLevels` |  | `8` | `null` | - |

## Rule levels in a profile

`ruleLevels` maps a rule id to `required`, `recommended` or `off`. The strict example makes these rules required: B-08, B-24, B-25, B-26, B-50, B-62, B-71.

## Extensions

An extension is an optional group of rules. It applies only when `extensions.<name>.enabled` is true: `walkability` (for consumers that place people or agents in rooms), `luminaires` (fixtures become lights), `signboards` (signs are generated from declared boards), `furnitureCollision` (furniture is approximated by a simple collider), `terrain` (the consumer's terrain source supplies the ground; the file carries a derived, read-only terrain patch). Rules that belong to an extension carry its name after the level, for example `B-90 REQUIRED luminaires`, and `rules.json` lists it in `extension`.

