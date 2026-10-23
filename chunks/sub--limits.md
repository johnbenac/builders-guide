<!-- chunk: sub--limits | source: 08-submissions-and-ingest.md | title: Limits | rules: - -->
## Limits

Defaults, all parameters of the profile (`submission` group, see `07-profile-parameters.md`): at most 200 files, 25 MiB per file, 100 MiB per
delivery; file types ifc, glb, png, jpg, json, md, csv and txt only (csv and txt exist because the room table and `SHA256SUMS.txt` need them);
no program, script, archive or executable file mode; no symbolic links; relative, portable, case-unique paths of at most 200 characters; images of
at most 64 million pixels. A consumer that accepts submissions can set other values in its own profile.
