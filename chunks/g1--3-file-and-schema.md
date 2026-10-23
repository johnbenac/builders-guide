<!-- chunk: g1--3-file-and-schema | source: 01-builders-and-architects-guide.md | title: 3. File and schema | rules: B-01,B-02,B-02a,B-03,B-04,B-05,B-06,B-07,B-08,B-09 -->
## 3. File and schema

**B-01 · REQUIRED** - Deliver an IFC schema edition the profile accepts (`schema.allowed`, default IFC4). Other editions may open in some tools, but files in an unlisted edition are not portable to that consumer.

**B-02 · REQUIRED** - Declare the length unit as metres (an `IfcSIUnit` `LENGTHUNIT` `METRE`, or a prefixed or conversion-based unit that resolves to metres) and model in it. A missing or misread unit rescales the whole building.

**B-02a · RECOMMENDED** - Prefer plain metres (a `METRE` unit with no prefix) over a prefixed or conversion-based unit, which some tools mishandle.

**B-03 · RECOMMENDED** - Deliver one coordinated master file per placement area, and send per-building files only as alternates. Several overlapping files for one area leave the consumer guessing which one is authoritative.

**B-04 · REQUIRED** - Keep the file plain ASCII: write every non-ASCII character with the format's escape (`\X2\00B7\X0\` for a middle dot, `\X2\2014\X0\` for a long dash). Raw bytes above 127 are read differently by different tools.

**B-05 · REQUIRED** - Stay within the profile's hard limits: `limits.maxFileMegabytes`, `limits.maxVertices` and `limits.maxTriangles`. A file over a consumer's cap is refused or truncated.

**B-06 · REQUIRED** - Use geometry that every common reader can display: swept solids (`IfcExtrudedAreaSolid` with rectangle, circle, arbitrary closed or arbitrary-with-voids profiles), faceted breps or polygonal face sets, and mapped items. Boolean-heavy breps, swept disks and unusual profiles are dropped by many readers without a message; `check_ifc.py` reports products that have a representation but yield no triangles.

**B-07 · RECOMMENDED** - Make the export deterministic: the same inputs give a byte-identical file (fixed timestamps, stable ordering, `GlobalId` values derived from stable keys). Consumers and reviewers compare revisions.

**B-08 · RECOMMENDED** - Write each STEP entity on a single line when the profile asks (`file.singleLineEntities`). Line-oriented tools, diff tools and simple readers handle such files; wrapped entities are valid but can be missed. A consumer that depends on it raises this rule to required.

**B-09 · RECOMMENDED** - Keep the file below the profile's recommended size, `budgets.recommendedFileMegabytes`. Large files load slowly and are hard to review.
