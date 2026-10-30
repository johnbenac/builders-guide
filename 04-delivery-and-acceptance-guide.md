<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Guide 4: Delivery and Acceptance Guide

For everyone who sends or receives work: how to package it, what the manifest says, how versions and licences are recorded,
how to check your own work before sending it, and how a receiving party accepts, returns or refuses it.

Rule levels and the profile mechanism are explained in the [README](README.md). The scripts named here are in
[tools/](tools/); each prints what it checked and exits with status 1 when a REQUIRED rule fails. "The receiving party" is
whoever takes the delivery: a consumer's operator, a client, an archive.

## 1. What you send

A delivery is one folder (and a zip of it) with these parts. Send only the parts your assignment needs.

```
example-room-1.0.0/
  manifest.json               what is in the package, with hashes (section 3)
  SHA256SUMS.txt              the same hashes in the plain checksum-file form
  ifc/
    example-room-master.ifc   the one coordinated master IFC file (buildings)
    alternates/               optional per-building files (not the master)
  tables/
    rooms.csv                 room table: ids, names, occupants, kinds (section 6)
    building.json             optional machine-readable building summary
  finishes/
    finish-schedule.json      what each colour and each floor means (guide 2)
    library.json              optional list of texture sets and the schedule
    SOURCES.csv               source and licence of every texture set
    textures/<set>/           albedo.png, normal.png, orm.png, set.json
  items/<itemId>/             <itemId>.ifc, <itemId>.item.json, optional preview.png (guide 3)
  terrain/                    only with the terrain extension: the height patch (patch.tif), its sidecar (patch.json),
                              and the site request (site-request.json) that produced it (guide 1, section 16)
  reports/                    the checker reports (section 5)
  notes/
    changes.md                what changed since the previous version
    open-points.md            anything you could not settle
```

**X-01 · REQUIRED** - Use this layout. Tools and reviewers find things by these folder names and roles. A building delivery has exactly one file under `ifc/` (not in `alternates/`).

**X-02 · RECOMMENDED** - Use lower-case ASCII file names without blanks, forward slashes in every path, and keep paths under 200 characters. Put nothing in the package that is not listed in the manifest.

## 2. Packaging the work

Build the package folder, write a short `package-meta.json` (start from `templates/package-meta.template.json`), and let the tool add the file list, hashes and sizes:

```
python3 tools/build_package.py init   example-room-1.0.0 package-meta.json
python3 tools/build_package.py verify example-room-1.0.0
```

`verify` is what a receiving party runs first, so run it yourself before sending.

## 3. The manifest

`manifest.json` has one entry for each of the following. Schema: `schemas/manifest.schema.json`.

| Field | Content |
|---|---|
| `format` | always `delivery-manifest/1` |
| `delivery` | `id` (lower case, dots and hyphens), `title`, `version` (SemVer), `created` (UTC date and time in the form `2026-10-22T10:00:00Z`), `supersedes` (the version it replaces, or null), `kind` (a list of `building`, `materials`, `furniture`, `mixed`) |
| `author` | `organisation`, `role` (who answers queries), `contact` (a role mailbox or handle; personal data is not needed) |
| `profile` | `name`, `version` (and optionally `sha256`) of the consumer profile you built and checked against |
| `frame` | `units` (`metres`), `axes`, `levelOffsetMetres`, `localZero` |
| `ifc` | `schema`, `entityNumberStart` |
| `files[]` | for each file: `path`, `role`, `sha256`, `bytes`, optional `version` |
| `terrain` | only with the terrain extension: `package` (`name`, `version`, `sha256` of the terrain source version used), `patch` (`path`, `sha256`), `sidecar` (`path`) |
| `counts` | numbers the checker found (levels, rooms, triangles ...) |
| `provenance[]` | for each asset group: `asset`, `type`, `source`, `author`, `licence`, `notes` |
| `licence` | `statement` that covers everything not listed in `provenance` |
| `checks` | `tool`, `toolVersion`, `report` (path in the package), `result` |

**X-10 · REQUIRED** - Put a `manifest.json` at the top of the package that matches the schema.

**X-11 · REQUIRED** - Record the SHA-256 hash (64 lower-case hexadecimal characters) and size in bytes of every file, and include a `SHA256SUMS.txt` in the plain two-column form (`hash`, two blanks, `path`). Hashes prove that what the receiving party holds is what you sent.

**X-12 · REQUIRED** - List every file in the package, and only those, in the manifest. (The manifest and the checksum file themselves are the exceptions.)

**X-13 · RECOMMENDED** - A building delivery has exactly one master IFC file (guide 1, B-03); other files are alternates.

**X-14 · REQUIRED** - Keep the whole package within the profile's cap, `package.maxPackageMegabytes`, when it sets one. Upload systems and mail gateways refuse larger packages.

**X-20 · REQUIRED** - Give every IFC file, texture set and library item a `provenance` entry (what it is, where it came from: `original`, `procedural` with the script and seed, or a named source; who made it; the licence that applies) when the profile requires provenance (`package.requireProvenance`, default true).

**X-21 · REQUIRED** - State a licence for every asset and a `licence.statement` for the package when the profile requires it (`package.requireLicence`, default true). A package whose licence terms are missing, or do not allow the receiving party to use, copy and adapt the work for the purpose of the assignment, cannot be accepted.

**X-23 · REQUIRED · terrain** - When the delivery has terrain, list the patch and its sidecar under `terrain/` with their roles, give each a provenance entry, and record the source package name, version and hash and the patch hash in the manifest `terrain` section, equal to what the sidecar states and to what the check report of the master file found in it, and keep the site request (its building origin, azimuth and floor height must be the file's). The terrain source can change between versions (shorelines in particular), so the delivery must say exactly which version its heights came from.

**X-22 · RECOMMENDED** - Deliver only content you are free to hand over. Do not include material that is restricted, reproduced from another party's work without permission, or that carries identifying marks of a third party. If part of your work is restricted, say so in `notes/open-points.md` and leave it out.

### Machine-readable summaries

Two optional files make a delivery readable without opening the model or the schedule. Both have JSON Schemas, and `check_all.py` validates them when present (a problem is a RECOMMENDED finding, rule X-41).

| File | Schema | Content |
|---|---|---|
| `tables/building.json` | `schemas/building-metadata.schema.json` | building id and name, frame, the master file, levels with elevations and room counts, occupants, room-id prefix |
| `finishes/library.json` | `schemas/material-library.schema.json` | the texture sets (name, version, path) and the finish schedule of a material delivery |

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

## 5. Acceptance checks

Acceptance is a list of checks. The first group is what you run yourself with the scripts; the second is what a receiving party typically checks, so you know what will be looked at.

### 5.1 Checks you run before sending

One command runs everything that applies to a deliverable and prints one JSON report (`schemas/check-report.schema.json`):
`python3 tools/check_all.py PATH --json --profile PROFILE.json`, where PATH is a master file, a `finishes/` folder, an `items/` folder or a package folder. Without `--profile` the default profile is used, and the report says which profile it checked against. Every tool below also takes `--json` and `--profile`. Exit codes: 0 no REQUIRED failure, 1 at least one, 2 wrong command line, 3 unreadable input. The loop for fixing findings is in `REPAIR-LOOP.md`.

```
python3 tools/check_all.py ifc/MASTER.ifc --profile PROFILE.json --json --out reports/check_all.json
python3 tools/check_ifc.py ifc/MASTER.ifc --profile PROFILE.json --finish-schedule finishes/finish-schedule.json --report reports/check_ifc.json
python3 tools/check_texture_set.py finishes/textures/SETNAME --preview wrap.png --report reports/check_texture_set.json
python3 tools/check_item.py items/ITEMID --report reports/check_item-ITEMID.json
python3 tools/build_package.py verify PACKAGE_FOLDER
```

| Script | What it checks | Rules |
|---|---|---|
| `check_all.py` | runs everything below that applies to the path | all |
| `check_ifc.py` | schema, units, text form, size and triangle limits, levels and containment, rooms (floor, identifiers, occupants, function), doorways, windows, floor slabs, stairs and risers, reservation volumes, zones, optional luminaire and signboard declarations, build volume, finish colours, identifiers | B-01 to B-120, D-03 to D-05 |
| `check_texture_set.py` | maps present, 8-bit RGB PNG, same square size, tangent-basis normal, packed occlusion-roughness-metalness, tile size, texel density, luminance, wrap seam, `set.json` fields | D-40 to D-49 |
| `check_item.py` | one item at the origin, class, declared dimensions against geometry, pivot, collision box, triangle budget, item id | F-01 to F-51 |
| `build_package.py verify` | manifest against the schema, every hash and size, no unlisted files, one master, package size, provenance and licence, the check report belongs to the master and passed | X-10 to X-40 |

**X-40 · REQUIRED** - Run `check_ifc.py` on the exact master file you are sending, with the profile, and include its JSON report in the package. The report records the SHA-256 of the master file it checked and the profile it used; a report for a different file is not accepted. A delivery with any REQUIRED failure in the report is not sent.

Findings have a fixed shape, which a receiving party also uses when it sends work back (section 7):

```json
{ "id": "B-41@1a2b3c4d", "rule": "B-41", "level": "REQUIRED", "status": "fail", "severity": "error",
  "location": { "file": "master.ifc", "element": "3Z2k6lcTnJFPCzw1CFlWEi" },
  "message": "IfcDoor Entrance door is not linked to an opening in a wall",
  "fix_hint": "Add an IfcOpeningElement in the wall with IfcRelVoidsElement ... and IfcRelFillsElement ..." }
```

`status` is `pass`, `info`, `warn` (a RECOMMENDED rule not met) or `fail` (a REQUIRED rule not met). `element` is the `GlobalId` of the product concerned.

Rules the script can only estimate say "estimate" in their message: the standing-point check (B-33), the sign text fit and legibility (B-101, B-102) and the riser check (B-61). A person confirms those.

### 5.2 Checks a receiving party typically makes

| # | Check | What it looks at | Rule |
|---|---|---|---|
| 1 | package intake | every hash and size, the layout, the manifest | X-10 to X-14 |
| 2 | reading | the master opens in an accepted schema edition with a metre length unit and within the limits | B-01, B-02, B-05 |
| 3 | identity | `GlobalId` values and entity numbers are unique across everything held; room and zone identifiers are unique | B-22, B-70, B-71, B-81 |
| 4 | rooms | each room has geometry and a floor; rooms can be classified | B-20 to B-26 |
| 5 | doorways | each door's opening is found, the rooms either side are listed, the opening is clear | B-41, B-42 |
| 6 | windows | window openings cut their walls | B-44 |
| 7 | standing points | (walkability extension) every room has a free standing point | B-33, B-50 |
| 8 | stairs and ramps | stairs connect levels; risers and slopes within the profile | B-60 to B-65 |
| 9 | reservation volumes | provisions are marked, not solid | B-80 |
| 10 | light fixtures | (luminaires extension) required properties, positions match | B-90 to B-93 |
| 11 | signs | (signboards extension) boards fit their text and are legible | B-100 to B-102 |
| 12 | materials | every colour has a finish; every named texture set exists with matching hashes | D-03, D-40 |
| 13 | build volume | no vertex outside the volume or inside a keep-out | B-110 |
| 14 | repeatability | the same input gives the same result; unchanged identifiers stay | B-07, B-75 |

## 6. Pre-submission checklist

Tick every line before sending. Lines marked R are REQUIRED rules; the others are RECOMMENDED.

**Profile and frame**
- [ ] R I know which profile I build for (or I used the default and said so) and the report names it.
- [ ] R The file is in an accepted schema edition, in metres, in the profile's frame (B-01, B-02, B-10).
- [ ] The file is in the placement the profile expects, and a `FrameNote` property says so (B-11, B-12).

**Structure**
- [ ] R Every level has a name and an elevation, and every element belongs to a level (B-13).
- [ ] R The file is ASCII only (B-04), within the limits (B-05), and every product yields triangles (B-06).
- [ ] R Every `GlobalId` is unique and stable (B-70). Entity numbers follow the profile's range when it assigns one (B-71).

**Rooms**
- [ ] R Every room is an `IfcSpace` with geometry and a flat floor (B-20, B-21).
- [ ] R `RoomId` values are unique and meet the profile (B-22, B-23); every room has one (B-26, required in profiles that say so).
- [ ] Every room has `Occupant` and `Function`, a full name, and areas and levels where known (B-24, B-25, B-27, B-28).
- [ ] Streets, paths and park areas are rooms too (B-29).
- [ ] The room table is complete (X-41).

**Fabric**
- [ ] R Doors and windows fill openings that void walls (B-41, B-44); doorways are clear (B-42).
- [ ] R Slab holes are openings (B-53); floors are slabs or sit on a floor the consumer supplies (B-50, B-51).
- [ ] R Every stair flight is an `IfcStairFlight` (B-60); every multi-level building has a stair (B-62).
- [ ] Risers and slopes are within the profile (B-61, B-64).
- [ ] Reservation volumes are marked (B-80, B-81).

**Optional extensions (only when the profile enables them)**
- [ ] R Luminaires: assemblies with housing and emissive part and all properties, in the consumer's global frame (B-90 to B-93).
- [ ] R Signboards: all properties, fitting text, honest reading distance (B-100 to B-102).
- [ ] R Walkability: free standing point in every room (B-33).

**Finishes and items**
- [ ] R Every (class, colour, opacity) combination is in the finish schedule (D-03).
- [ ] R Every texture set has its maps and `set.json` with `tileMetres` (D-40, D-41, D-43).
- [ ] I looked at the three-by-three wrap preview of every texture (D-42, D-50).
- [ ] Items are modelled to the guide: class, pivot, collision (F-01, F-21, F-40).

**Package**
- [ ] R The manifest, hashes, provenance and licences are complete; `build_package.py verify` passes (X-10 to X-21).
- [ ] R The check report is for the exact master file and the profile used, and shows no REQUIRED failure (X-40).
- [ ] The version number follows the table in section 4, and `notes/changes.md` is written (X-30 to X-32).
- [ ] `notes/open-points.md` lists anything I could not settle.

**X-41 · RECOMMENDED** - Deliver `tables/rooms.csv` with the columns `roomId`, `name`, `occupant`, `kind` (`room`, `circulation`, `observation`, `open`), `enclosed` (`yes` or `no`), `level`, `levelElevationMetres`, `floorAreaM2`, `clearHeightM`, `buildingId` and `layer`, and list every new `Occupant` string with the room-id prefix that goes with it and its kind, so a receiving party can add its rules before intake. Open areas are listed as rooms too. A starting file is in `templates/rooms.template.csv`.

## 7. How a receiving party accepts, returns or refuses

### 7.1 Outcomes

| Outcome | When | What the sender receives |
|---|---|---|
| **Accepted** | every check in section 5 passes and review finds nothing to change | a confirmation naming the delivery id, version and the master file's hash |
| **Accepted with notes** | every REQUIRED rule passes, and the reviewer lists RECOMMENDED rules or defects worth fixing later | the same confirmation plus a findings list |
| **Revision needed** | one or more REQUIRED rules fail, or a defect makes the work unusable, but the delivery is otherwise sound | a findings list (section 7.3); the sender sends a new version |
| **Rejected** | the package cannot be used as it stands: a hash does not match, the file cannot be read, the schema or units are wrong, a hard limit is exceeded, the licence is missing or does not allow use, or the work was built to the wrong profile | the reason, and what to do before sending anything again |

### 7.2 Steps

1. **Intake.** Package checks (hashes, layout, manifest, provenance, licence). A failure here is a rejection or an immediate return, because nothing else can be trusted.
2. **Reading and identity.** The master file is read; units, limits, identifiers.
3. **Rule data.** For any new `Occupant` string or room-id prefix in the room table, the receiving party adds its classification rules, and renames declaration properties to its own names with `tools/map_properties.py` and a mapping file it keeps itself (a profile's `propertyNames` and `propertyValues` are exactly that mapping). The sender's file stays neutral.
4. **Build and check.** The receiving party builds from the files and runs the checks of section 5.2.
5. **Review.** A person looks at finishes and wrap, signs, lighting, furniture clearances, and anything the scripts only estimate.
6. **Outcome.** One of the four outcomes above.

### 7.3 Findings and revision

The receiving party sends findings in the shape of section 5.1: the rule, its level, the product's `GlobalId`, and what was measured against what was expected. The sender answers each REQUIRED finding with a fix or a reason.

**X-60 · RECOMMENDED** - When you send a revision, change only what the findings and your own notes name, bump the version (section 4), list what changed in `notes/changes.md`, and keep every unchanged identifier. A revision that renames identifiers without being asked is a MAJOR change and is reviewed again from the start.

### 7.4 After acceptance

An accepted version is held by its hashes. If you later replace a building, deliver a new version of the master file that keeps the identifiers of everything that stays; references the receiving party holds (which room is a start room, which sign belongs to which building) then keep working. Nothing in an accepted version is edited by the receiving party: if it needs a change, it asks for a new version.

## 8. Submitting a delivery as a pull request

Outside contributors can offer a delivery (a building, interior, furniture, materials, fixtures or hardware) to this repository. The process, in
one line: fork the repository, build the delivery in a branch of your fork under `deliveries/<slug>/`, and open a pull request against `main`.
`08-submissions-and-ingest.md` walks through it; this section holds the rules the checks enforce. Limits are the `submission` group of the
profile (`07-profile-parameters.md`); the numbers below are the defaults.

A submitted delivery is an ordinary package (section 1) with three differences: its folder is `deliveries/<slug>/` and the slug equals
`delivery.id`; its manifest is named `delivery.json` and carries an extra `submission` object (`schemas/submission.schema.json`); and it may
hold preview pictures under `previews/`. `python3 tools/check_submission.py deliveries/<slug>` checks the form,
`python3 tools/check_all.py deliveries/<slug>` checks everything (it runs `check_submission.py` and the package checks).

**X-70 · REQUIRED** - Put a submitted delivery in `deliveries/<slug>/` with a `delivery.json` whose `delivery.id` equals the slug and whose `submission` object states the title, the submitter handle, the licence, the profile used, the tool versions and the attestation. Reviewers and the intake tool find a delivery by its folder and its manifest, and a handle ties it to its author.

**X-71 · REQUIRED** - Offer the delivery under a licence the profile lists (`submission.allowedLicences`; by default CC BY 4.0, or CC0 when the delivery says so). A delivery under other terms cannot be taken in, because anyone who uses a catalogue entry later needs the terms to be uniform and known.

**X-72 · REQUIRED** - Include only files of the types the profile lists (`submission.allowedExtensions`; by default ifc, glb, png, jpg, json, md, csv and txt), with no program, script or archive and no executable file mode. A delivery is data; anything that can run or unpack itself is a risk for every person and tool that opens the delivery.

**X-73 · REQUIRED** - Keep a delivery within the profile's limits: at most `submission.maxFiles` files (200), `submission.maxFileBytes` per file (25 MiB) and `submission.maxDeliveryBytes` in total (100 MiB). Review and intake run on shared machines with fixed time and memory.

**X-74 · REQUIRED** - Use only relative, portable paths: no leading slash, no `..`, no backslash or drive letter, names of letters, digits, dot, hyphen and underscore that do not start with a dot, no reserved device names, no two names that differ only by case, and no path longer than `submission.maxPathLength`, in the folder and in every path the manifest and the checksum list name. A path that leaves the delivery folder or collides on another system can overwrite or hide a file.

**X-75 · REQUIRED** - Include no symbolic link and no special file, only plain files and folders. A link can point outside the delivery and make a reader open a file that was never submitted.

**X-76 · REQUIRED** - Have the submitter attest in `submission.attestation` that the work is their own or they may offer it, that they may license it under the stated licence, and that it holds no restricted third-party content. The maintainers cannot check ownership, so the statement is on record with the delivery.

**X-77 · REQUIRED** - Make every file what its name says: PNG and JPEG images that are real images within `submission.maxImagePixels`, GLB files that are binary glTF 2 of the stated length, IFC files that are IFC text files, JSON that parses, text in UTF-8 without NUL bytes or active markup (script, iframe, object, embed). A renamed file can hide content from review and can crash a reader.

**X-78 · RECOMMENDED** - Add at least one preview picture under `previews/` (or `items/<id>/preview.png`) so a reviewer sees the work before opening a model.

### 8.1 Proofs: models and pictures that anyone can reproduce

A reviewer should not have to open a modelling program to see what a delivery is. Every submitted delivery therefore carries **proofs** in
`proofs/`: binary glTF (GLB) exports of the whole model and of every component, a validation report for those exports, and a standard set of
rendered pictures, all tied together by `proofs/manifest.json` (`schemas/proofs.schema.json`, format `proofs/1`). One command makes them:
`python3 tools/build_proofs.py deliveries/<slug>` (export with `tools/export_glb.py`, validation with `tools/validate_glb.py`, pictures with
`tools/render.py`); `python3 tools/check_proofs.py deliveries/<slug> --reproduce` checks them and rebuilds them to compare. Everything runs
without a graphics card or a display, so the same files come out on a laptop and on a build server. The limits are the `proofs` group of the
profile (`07-profile-parameters.md`); the numbers below are the defaults.

The GLB files use metres and Y up: a point of the IFC frame (Z up) becomes `(x, y, z) -> (x, z, -y)`. Colours become PBR metallic-roughness
materials; a texture set becomes a swatch with its maps embedded. Zones and reservation volumes state a requirement, not a thing: when the
profile sets `proofs.glbVolumes` to `exclude` (or `export_glb.py --volumes exclude` is used), they get no mesh and no node and are listed in the
`extras.excluded` of the whole-model GLB, which `validate_glb.py --ifc` accepts as the written reason for a missing node (only those two kinds,
never a wall or a slab). A consumer that moves or turns single things (a door about its hinge, a chair) sets `proofs.glbPivots` to `placement`: each
product then has its own origin, the node carries the placement, identical shapes share one mesh, and `model.placements.json` lists every node; a profile
may also ask for indexed meshes (`proofs.glbIndexed`). Two surfaces in one plane facing the same way fight for the same pixels (z-fighting);
`validate_glb.py` warns when two nodes share more than `budgets.coincidentFaceMinAreaM2` of such area (an estimate, RECOMMENDED), `tools/coplanar.py`
lists the pairs, and `proofs.glbCoplanar` set to `union` merges the overlaps inside one product. The pictures use fixed lighting and a fixed background and are always made
from the delivered GLB files, never from anything else: a plan per level (cut at 1.2 m above the floor), four interior views for each room kind
that is present, four exterior views, and for every component a contact sheet of turntable frames (a swatch view for a texture set).

**X-79 · REQUIRED** - Put a proof manifest at `proofs/manifest.json` (format `proofs/1`) that lists every GLB, the GLB validation report and every render with its SHA-256, size and the tool and version that made it, and put nothing else in `proofs/`. A reviewer, a catalogue and the intake tool need one file that says exactly which models and pictures belong to which source, and a way to see that none was changed afterwards.

**X-80 · REQUIRED** - Make every delivered GLB a valid binary glTF 2 file in metres with Y up, with no external reference, no unused buffer, image or material, finite and unit-length normals, tangents where a normal map is used, named scene-graph nodes, and the node, triangle and texture limits of the profile. A GLB that is malformed, in another unit or axis, or that points outside itself shows a consumer a different building than the IFC file does, or crashes it.

**X-81 · REQUIRED** - Deliver a GLB of the whole master model and one of every item, covering, fixture, hardware piece, door, window and texture set, each made from the delivered IFC files (their SHA-256 is recorded), together with a validation report that passes and names every GLB by its SHA-256. The GLB files are what the pictures are made from and what a consumer without an IFC reader opens, so they must correspond to the delivered source and be known to be valid.

**X-82 · REQUIRED** - Include renders that cover every level (a plan), every room kind present (the profile's number of interior views), the outside of the building, and every item, covering, fixture, hardware piece, door, window and texture set (a contact sheet). A picture set that leaves out a level, a kind of room or a component lets a defect there go unseen.

**X-83 · REQUIRED** - Make every render from a GLB of the delivery and record in the manifest the SHA-256 of that GLB, of the picture itself, its pixel size, the camera and the lighting; each recorded GLB hash must be the hash of the delivered GLB file. A picture that cannot be traced to the exact model it shows proves nothing about it.

**X-84 · REQUIRED** - Keep every render within the profile's pixel and file-size limits (`proofs.minRenderWidth`, `proofs.maxRenderPixels`, `proofs.maxRenderBytes`) and the whole `proofs/` folder within `proofs.maxProofBytes`. Pictures are for looking at on shared machines; a very large one costs every reviewer, and a tiny one shows nothing.

**X-85 · REQUIRED** - Keep personal data and local paths out of images and GLB files: renders hold only the image chunks the profile allows, no image holds EXIF, XMP, a colour profile with text or text that names a person, a folder, a host or an address, and no GLB holds a path, an address, an e-mail address or a generator other than the set's. A file that records who made it, where, or on which machine leaks that to everyone who receives the delivery.

**X-86 · REQUIRED** - Make the proofs reproducible: rebuilding the GLB files from the delivered IFC files must give the same bytes, and re-rendering the delivered GLB files must give pictures that differ from the delivered ones by no more than `proofs.renderTolerance`; where the toolchain is not available the check says so and is skipped, not passed. Proofs that cannot be reproduced cannot be trusted, and a rebuild is the cheapest way to see that the pictures do show the model.

Acceptance of a submission is a merge to `main`; see `08-submissions-and-ingest.md` for what happens next. The checks cannot judge quality,
ownership or taste: a person reviews those, and may decline a delivery that passes every check.

### 8.2 Consumer appearance and remote review

A reproducible proof is not automatically a useful visual review. Follow [guide 9](09-environment-review-and-handoff.md): inspect every authored space and connection, construction/detail closeups and actual exported materials in the intended consumer. Record renderer/light substitutions explicitly. Keep technical validity, rendered appearance and device behavior separate, and attach revision-bound findings and a resumable handoff.
