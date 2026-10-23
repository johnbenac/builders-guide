<!-- chunk: sub--what-a-delivery-folder-holds | source: 08-submissions-and-ingest.md | title: What a delivery folder holds | rules: - -->
## What a delivery folder holds

A delivery is an ordinary package (guide 4, section 1) with these differences:

```
deliveries/oak-study/
  delivery.json            the manifest (schemas/manifest.schema.json) plus a `submission` object (schemas/submission.schema.json)
  SHA256SUMS.txt           hashes of every file, as in any package
  ifc/<name>-master.ifc    the master IFC file, when the delivery has a building or room
  items/<itemId>/          furniture, fixtures and hardware as items (guide 3): <itemId>.ifc and <itemId>.item.json
  finishes/                finish schedule, library.json and textures/<set>/ (guide 2)
  previews/                pictures of the work (png or jpg) so a reviewer sees it first
  reports/ notes/ tables/  the check reports, the change notes and the room table, as in guide 4
```

`delivery.json` is built with `python3 tools/build_package.py init DIR meta.json --manifest-name delivery.json`; the meta file carries the
`delivery`, `author`, `profile`, `frame`, `provenance`, `licence` and `checks` parts of guide 4, section 3, and the `submission` object:

| Field | Content |
|---|---|
| `title`, `summary` | what the delivery is, in a sentence |
| `submitter.handle` | the account the pull request is opened from (no personal data is needed) |
| `licence` | `CC-BY-4.0` (the default), or `CC0-1.0` when the delivery says so; the profile lists the licences it takes |
| `profile` | name and version of the profile the delivery was checked against |
| `toolVersions` | the tools and libraries used (this guide set's version, the IFC library) |
| `attestation` | `ownWork`, `mayLicense`, `noRestrictedContent`, all `true` |

Contributed assets are offered under CC BY 4.0 unless the delivery states CC0. By opening the pull request the contributor attests that they
own the work or may license it, and that it contains no restricted third-party content (X-22, X-76).
