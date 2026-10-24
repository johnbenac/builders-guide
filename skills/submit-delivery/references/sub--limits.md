<!-- chunk: sub--limits | source: 08-submissions-and-ingest.md | title: Limits | rules: - -->
## Limits

Defaults, all parameters of the profile (`submission` and `proofs` groups, see `07-profile-parameters.md`): at most 600 files (proofs add a GLB and a sheet for every component; it was 200 before 2.3.0), 25 MiB per file, 100 MiB per
delivery; file types ifc, glb, png, jpg, json, md, csv and txt only (csv and txt exist because the room table and `SHA256SUMS.txt` need them);
no program, script, archive or executable file mode; no symbolic links; relative, portable, case-unique paths of at most 200 characters; images of
at most 64 million pixels; renders of at least 256 and at most about 2 million pixels and 3 MiB, and `proofs/` of at most 64 MiB. A consumer that accepts submissions can set other values in its own profile.
