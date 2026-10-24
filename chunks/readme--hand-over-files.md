<!-- chunk: readme--hand-over-files | source: README.md | title: Hand-over files | rules: - -->
## Hand-over files

[dist/](dist/) holds the single-file versions:

| File | Content |
|---|---|
| `builders-guide-2.3.0.pdf` | all guides, the worked example, the submissions page and the rules index in one document |
| `builders-guide-2.3.0.html` | the same, as one web page |
| `builders-guide-2.3.0.zip` | the whole set, with `MANIFEST.sha256` |
| `SHA256SUMS.txt`, `builders-guide-2.3.0.zip.sha256` | SHA-256 of the three files above |

`MANIFEST.sha256` lists the SHA-256 of every other file in the set (`sha256sum -c MANIFEST.sha256`); `MANIFEST.json` describes the same files
with purpose and tags. `tools/build_dist.py` rebuilds all of this.
