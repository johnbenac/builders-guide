// SPDX-License-Identifier: Apache-2.0
// Runs the Khronos glTF Validator (npm package gltf-validator, Apache-2.0, pinned in package-lock.json) on GLB files.
//   node tools/khronos/validate.mjs FILE.glb [FILE.glb ...]   prints one JSON array: {file, version, errors, warnings, infos, hints, messages}
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const require = createRequire(join(dirname(fileURLToPath(import.meta.url)), "package.json"));
const validator = require("gltf-validator");
const out = [];
for (const f of process.argv.slice(2)) {
  const report = await validator.validateBytes(new Uint8Array(readFileSync(f)), { uri: basename(f), maxIssues: 200 });
  const i = report.issues;
  out.push({
    file: f, version: validator.version(),
    errors: i.numErrors, warnings: i.numWarnings, infos: i.numInfos, hints: i.numHints,
    messages: i.messages.map((m) => ({ code: m.code, severity: m.severity, pointer: m.pointer || "", message: m.message })),
  });
}
console.log(JSON.stringify(out));
