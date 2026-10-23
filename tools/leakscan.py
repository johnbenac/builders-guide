# SPDX-License-Identifier: Apache-2.0
"""Public-safety scan: finds machine-local addresses and paths in the files of the set, in the hand-over documents and inside them
(zip members, PDF streams and link actions). Used by test_sync.py; also usable alone:

    python3 tools/leakscan.py [ROOT]

It looks for a local-file address, an absolute Unix path that starts at a home, media, mount, server or root folder, and a drive-letter
path. It holds no list of names: the set is application-neutral, so what must not appear is where a build ran, not who built it.
"""
import io
import os
import re
import sys
import zipfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileset  # noqa: E402

_SCHEME = "file" + ":" + "//"
PATTERNS = [
    ("local-file address", re.compile(re.escape(_SCHEME).encode(), re.I)),
    ("absolute path", re.compile(rb"(?<![\w.~-])/(?:" + b"|".join(re.escape(x.encode()) for x in
                                  ("media", "home", "srv", "root", "Users", "mnt")) + rb")/")),
    ("drive-letter path", re.compile(rb"(?<![\w])[A-Za-z]:[\\/][A-Za-z0-9_.$-]{2,}[\\/]")),
]


def scan_bytes(data, where, binary=False):
    """Findings (where, kind, excerpt) in one blob. `binary` skips the drive-letter pattern (random bytes match it by chance)."""
    out = []
    for kind, rx in PATTERNS:
        if binary and kind == "drive-letter path":
            continue
        for m in rx.finditer(data):
            out.append((where, kind, data[max(0, m.start() - 12):m.end() + 24].decode("latin-1")))
    return out


def scan_pdf(data, where):
    out = scan_bytes(data, where, binary=True)
    for m in re.finditer(rb"stream\r?\n", data):         # every deflate stream, decompressed
        try:
            out += scan_bytes(zlib.decompressobj().decompress(data[m.end():]), where + " (stream)")
        except zlib.error:
            pass
    try:
        import pikepdf
    except ImportError:
        return out
    with pikepdf.open(io.BytesIO(data)) as pdf:
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Stream):
                try:
                    out += scan_bytes(obj.read_bytes(), where + " (decoded stream)")
                except Exception:
                    pass
            elif isinstance(obj, (pikepdf.Dictionary, pikepdf.Array)):
                out += scan_bytes(repr(obj).encode("latin-1", "replace"), where + " (object)")
        out += scan_bytes(repr(pdf.docinfo).encode("latin-1", "replace"), where + " (info)")
    return out


def scan_blob(data, where):
    if data[:5] == b"%PDF-":
        return scan_pdf(data, where)
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                out = scan_bytes("\n".join(z.namelist()).encode(), where + " (member names)")
                for n in z.namelist():
                    out += scan_blob(z.read(n), "%s:%s" % (where, n))
                return out
        except zipfile.BadZipFile:
            pass
    return scan_bytes(data, where, binary=b"\0" in data[:4096])


def scan_tree(root):
    out = []
    rels = fileset.set_files(root) + [fileset.CHECKSUM_FILE]
    d = os.path.join(root, "dist")
    if os.path.isdir(d):
        rels += ["dist/" + n for n in sorted(os.listdir(d))]
    for rel in rels:
        with open(os.path.join(root, rel), "rb") as fh:
            out += scan_blob(fh.read(), rel)
        out += scan_bytes(rel.encode(), rel + " (name)")
    return out


if __name__ == "__main__":
    found = scan_tree(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    for w, k, x in found[:40]:
        print("%s: %s: %r" % (w, k, x))
    print("leakscan: %s" % ("FAIL (%d)" % len(found) if found else "ok"))
    sys.exit(1 if found else 0)
