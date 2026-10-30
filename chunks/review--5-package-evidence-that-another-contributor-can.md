<!-- chunk: review--5-package-evidence-that-another-contributor-can | source: 09-environment-review-and-handoff.md | title: 5. Package evidence that another contributor can continue | rules: - -->
## 5. Package evidence that another contributor can continue

For each finding record severity, affected objects/rooms, observation, artifact
hashes, correction owner, attempted fix and the matching verification view. Keep
baseline and candidate evidence separate. A changed artifact invalidates its old
acceptance; record a superseding decision rather than editing away adverse evidence.

| Change | Evidence to revisit |
|---|---|
| Geometry or pose | Collision/support, connectivity, room stops, UVs, bake, media and consumer integration |
| Materials or source UVs | Export/import parity, relevant bake contributions, optical closeups and media |
| Renderer, sky or lighting | Matched views, affected media and device measurements |
| Encoding/optimization | Decoded pixels/surfaces, attribute retention and consumer views |
| Labels or publication only | Affected links, accessibility, asset integrity and deployed behavior |

Reuse a prior geometry/navigation result for a material-only revision only when
an explicit equivalence check proves unchanged relevant geometry and poses. A
matching vertex count is insufficient; changed triangle diagonals can matter.

Record reviewer independence and limits. Schema validation, image existence,
reproducibility and visual acceptance are separate results. A diagnostic render,
software renderer or emulated phone must not be represented as a physical-device test.
Measure actual transfer, first usable frame, frame times and repeated-entry resource
cleanup. Optimize from evidence without hiding quality loss or inventing a universal limit.
