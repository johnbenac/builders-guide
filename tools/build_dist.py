#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the hand-over files: one combined HTML, one combined PDF, a zip of the whole set and their checksums.

    python3 tools/build_dist.py

Needs `pandoc`, a Chromium-based browser (`google-chrome`) on the path and `pikepdf` (tools/requirements-dist.txt). Writes into dist/:
    builders-guide-1.0.0.html, builders-guide-1.0.0.pdf, builders-guide-1.0.0.zip, builders-guide-1.0.0.zip.sha256, SHA256SUMS.txt
and MANIFEST.sha256 (the hash of every file in the set) at the top.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileset  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
VERSION = "2.1.0"
NAME = "builders-guide-" + VERSION
DIST = os.path.join(ROOT, "dist")
ORDER = ["README.md", "AGENTS.md", "01-builders-and-architects-guide.md", "02-interior-decorators-guide.md",
         "03-furniture-and-fixtures-guide.md", "04-delivery-and-acceptance-guide.md", "05-worked-example.md", "REPAIR-LOOP.md", "06-rules-index.md"]


def slug(title):
    s = re.sub(r"[^\w\- ]", "", title.lower().replace("`", "")).strip()
    return re.sub(r" ", "-", s)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def combined_markdown():
    anchors = {}
    texts = {}
    for fn in ORDER:
        with open(os.path.join(ROOT, fn), encoding="utf-8") as fh:
            t = fh.read()
        texts[fn] = t
        first = next(ln for ln in t.split("\n") if ln.startswith("# "))
        anchors[fn] = slug(first[2:])
    out = []
    for fn in ORDER:
        t = texts[fn]
        # links to other guides become in-document links; links to folders become plain text
        t = re.sub(r"\[([^\]]+)\]\(([0-9A-Za-z._-]+\.md)\)", lambda m: "[%s](#%s)" % (m.group(1), anchors.get(m.group(2), "")), t)
        t = re.sub(r"\[([^\]]+)\]\((?:templates|tools|schemas|dist)/[^)]*\)", r"\1", t)
        # wrap long lines inside fenced code blocks (the page is narrower than a terminal)
        lines, inside = [], False
        for ln in t.split("\n"):
            if ln.startswith("```"):
                inside = not inside
                lines.append(ln)
            elif inside and len(ln) > 100:
                lines.extend(textwrap.wrap(ln, 100, subsequent_indent="    ", break_long_words=True, break_on_hyphens=False) or [ln])
            else:
                lines.append(ln)
        out.append("\n".join(lines))
    return "\n\n".join(out) + "\n"


def scrub_pdf(src, dst):
    """Copy a PDF, removing every URI action that is not http(s) or mailto (a local-file link would record a path of this machine)."""
    import pikepdf
    with pikepdf.open(src) as doc:
        for page in doc.pages:
            if "/Annots" not in page:
                continue
            keep = []
            for a in page.Annots:
                act = a.get("/A")
                uri = str(act.get("/URI", "")) if act is not None else ""
                if uri and not re.match(r"(https?:|mailto:)", uri):
                    continue
                keep.append(a)
            page.Annots = doc.make_indirect(pikepdf.Array(keep))
        doc.save(dst, deterministic_id=True)


def main():
    os.makedirs(DIST, exist_ok=True)
    for n in os.listdir(DIST):                      # earlier outputs are rebuilt, never checked or kept
        os.remove(os.path.join(DIST, n))
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_all.py"), "--write"], check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "test_sync.py")], check=True)
    md = os.path.join(DIST, NAME + ".combined.md")
    with open(md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(combined_markdown())
    html = os.path.join(DIST, NAME + ".html")
    subprocess.run(["pandoc", "-f", "gfm", "-t", "html5", "--template", os.path.join(ROOT, "tools", "template.html"), "--toc",
                    "--toc-depth=2", "-M", "title=Authoring Guide Set for Digital Buildings, Materials and Furniture (IFC)",
                    "-M", "subtitle=Version %s, 2026-10-23. Application-neutral guides and tools for outside organisations and their agents." % VERSION,
                    "-M", "toc=true", md, "-o", html], check=True)
    os.remove(md)
    pdf = os.path.join(DIST, NAME + ".pdf")
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        sys.exit("no Chromium-based browser found for the PDF")
    # Render from a neutral temporary folder with the HTML copied in, so that the browser never records a path of this machine,
    # then drop every link annotation that is not an in-document link or a web address (a local-file link would leak a path).
    import tempfile
    with tempfile.TemporaryDirectory(prefix="render-") as tmp:
        shutil.copyfile(html, os.path.join(tmp, "guide.html"))
        out_pdf = os.path.join(tmp, "guide.pdf")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--print-to-pdf=" + out_pdf,
                        "guide.html"], check=True, cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        scrub_pdf(out_pdf, pdf)
    # the file list of the set
    members = fileset.set_files(ROOT) + fileset.dist_files(ROOT)      # the same list as MANIFEST.json and MANIFEST.sha256
    with open(os.path.join(ROOT, fileset.CHECKSUM_FILE), "w", newline="\n") as fh:
        fh.write(fileset.checksum_text(ROOT))
    zpath = os.path.join(DIST, NAME + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(members + ["MANIFEST.sha256"]):
            zi = zipfile.ZipInfo(NAME + "/" + rel, date_time=(2026, 10, 23, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (0o755 if rel.startswith("tools/") and rel.endswith(".py") else 0o644) << 16
            with open(os.path.join(ROOT, rel), "rb") as fh:
                z.writestr(zi, fh.read())
    with open(zpath + ".sha256", "w", newline="\n") as fh:
        fh.write("%s  %s\n" % (sha(zpath), os.path.basename(zpath)))
    with open(os.path.join(DIST, "SHA256SUMS.txt"), "w", newline="\n") as fh:
        for p in (zpath, html, pdf):
            fh.write("%s  %s\n" % (sha(p), os.path.basename(p)))
    print("built", ", ".join(os.path.basename(p) for p in (html, pdf, zpath)))


if __name__ == "__main__":
    main()
