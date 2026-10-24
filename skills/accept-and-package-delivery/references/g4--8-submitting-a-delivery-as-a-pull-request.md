<!-- chunk: g4--8-submitting-a-delivery-as-a-pull-request | source: 04-delivery-and-acceptance-guide.md | title: 8. Submitting a delivery as a pull request | rules: X-70,X-71,X-72,X-73,X-74,X-75,X-76,X-77,X-78 -->
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
