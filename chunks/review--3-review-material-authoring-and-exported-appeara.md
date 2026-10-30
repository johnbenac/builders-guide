<!-- chunk: review--3-review-material-authoring-and-exported-appeara | source: 09-environment-review-and-handoff.md | title: 3. Review material authoring and exported appearance separately | rules: - -->
## 3. Review material authoring and exported appearance separately

Name the intended surface: paint, wood species, metal/coating, plaster, glass,
fabric, stone, foliage. A solid painted finish is often correct; do not substitute
a generic timber or noise texture merely because the exporter has one available.

Check UV orientation, real scale, repetition and seams at corners and close range.
Inspect color, normal, roughness, metallic, emission and optical properties after
export and import into the intended consumer. Retain material identity through
batching. Texture-cache keys must include settings that change the resulting material.

Alpha coverage alone does not establish believable clear glass. Preserve the
source's intended transmission, index of refraction and roughness using supported
properties; keep mirror and painted/opaque surfaces distinct. Record unsupported
features. Do not silently replace materials by name in a proof renderer: that can
make a broken export appear correct. Label diagnostic fill lights and substitutions;
they cannot prove the unmodified consumer's appearance.
