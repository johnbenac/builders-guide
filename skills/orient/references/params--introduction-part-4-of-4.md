<!-- chunk: params--introduction-part-4-of-4 | source: 07-profile-parameters.md | title: Introduction (part 4 of 4) | rules: - -->
| Parameter | Meaning | default | strict | Rules |
|---|---|---|---|---|
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
