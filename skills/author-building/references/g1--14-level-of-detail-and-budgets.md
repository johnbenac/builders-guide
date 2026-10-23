<!-- chunk: g1--14-level-of-detail-and-budgets | source: 01-builders-and-architects-guide.md | title: 14. Level of detail and budgets | rules: B-120,B-121 -->
## 14. Level of detail and budgets

Triangle count drives load time; the number of distinct materials and objects drives drawing cost. Hard caps are `limits.*` (B-05); recommended sizes are `budgets.*`.

| Quantity | Profile parameter | Default |
|---|---|---|
| file size, hard | `limits.maxFileMegabytes` | 250 MB |
| vertices, hard | `limits.maxVertices` | 10,000,000 |
| triangles, hard | `limits.maxTriangles` | 5,000,000 |
| file size, recommended | `budgets.recommendedFileMegabytes` | 100 MB |
| triangles, recommended | `budgets.recommendedTriangles` | 1,000,000 |
| distinct (class, colour, opacity) combinations | `budgets.maxDistinctColours` | 50 |

**B-120 · RECOMMENDED** - Stay under the profile's recommended triangle count, `budgets.recommendedTriangles`. A constrained consumer publishes a much lower figure; build to the profile you were given. Terrain triangles are counted separately (B-138).

**B-121 · RECOMMENDED** - Spend triangles where the viewer looks: entrances, interiors a person stands in, anything within arm's reach. Distant detail is wasted.
