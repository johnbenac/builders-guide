<!-- chunk: g4--4-versions | source: 04-delivery-and-acceptance-guide.md | title: 4. Versions | rules: X-30,X-31,X-32,X-50 -->
## 4. Versions

**X-30 · RECOMMENDED** - Version the delivery, each texture set and each item with SemVer (`MAJOR.MINOR.PATCH`), and give every version a creation time. A version is the exact set of bytes in its manifest.

**X-31 · RECOMMENDED** - Choose the next version number by what changed.

| Change | Example | Next version |
|---|---|---|
| corrections that change no identifier and no meaning | a wrong door height fixed, a colour nudged | PATCH (1.0.0 to 1.0.1) |
| added content with every existing identifier unchanged | a new room, a new item, a new finish | MINOR (1.0.1 to 1.1.0) |
| anything that renames, removes or re-means an identifier, or changes the frame | a room id changed, a level moved | MAJOR (1.1.0 to 2.0.0) |

**X-32 · RECOMMENDED** - Write `notes/changes.md`: for each version, the ids added, changed and removed, in plain sentences.

**X-50 · REQUIRED** - Never change a delivered version in place. A correction is a new version with a new manifest and new hashes; two different files must never carry the same version number.
