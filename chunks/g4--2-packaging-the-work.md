<!-- chunk: g4--2-packaging-the-work | source: 04-delivery-and-acceptance-guide.md | title: 2. Packaging the work | rules: - -->
## 2. Packaging the work

Build the package folder, write a short `package-meta.json` (start from `templates/package-meta.template.json`), and let the tool add the file list, hashes and sizes:

```
python3 tools/build_package.py init   example-room-1.0.0 package-meta.json
python3 tools/build_package.py verify example-room-1.0.0
```

`verify` is what a receiving party runs first, so run it yourself before sending.
