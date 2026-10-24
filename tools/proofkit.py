# SPDX-License-Identifier: Apache-2.0
"""Shared helpers of the proof tools (check_proofs.py, validate_glb.py, render.py, build_proofs.py): reading PNG and JPEG structure,
looking for personal data and local paths in metadata, and comparing two pictures. Not a command-line tool.
"""
import json
import re
import struct
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
# chunks a render may hold: the image itself and its physical size / colour declaration. Anything else (text, time, colour profile, EXIF)
# could carry a name, a path or a date and is not needed.
RENDER_CHUNKS = {b"IHDR", b"IDAT", b"IEND", b"PLTE", b"tRNS", b"sRGB", b"gAMA", b"pHYs"}
TEXT_CHUNKS = {b"tEXt", b"zTXt", b"iTXt"}
META_CHUNKS = TEXT_CHUNKS | {b"eXIf", b"iCCP", b"tIME"}
PERSONAL_KEYS = re.compile(r"^(author|artist|creator|copyright|owner|email|e-mail|user|username|host|hostname|machine|computer|location|gps|"
                           r"source|comment|description|title|software)$", re.I)

_SCHEME = "file" + ":"
LEAK = [
    ("local-file address", re.compile(re.escape(_SCHEME) + r"/{1,3}", re.I)),
    ("absolute path", re.compile(r"(?<![\w.~-])/(?:media|home|srv|root|Users|mnt|tmp|var|opt|etc|usr|private|Volumes)/")),
    ("home path", re.compile(r"(?<![\w])~[/\\]")),
    ("drive-letter path", re.compile(r"(?<![\w])[A-Za-z]:[\\/][A-Za-z0-9_.$ -]{2,}")),
    ("network path", re.compile(r"(?<![\w:])\\\\[A-Za-z0-9_.-]+\\")),
    ("address with a host", re.compile(r"\b[a-z][a-z0-9+.-]{1,12}://[^\s\"']+", re.I)),
    ("e-mail address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b")),
    ("IPv4 address", re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")),
]


def find_leaks(text):
    """[(kind, excerpt)] for every personal-data or local-path pattern in a string."""
    out = []
    for kind, rx in LEAK:
        for m in rx.finditer(text):
            out.append((kind, text[max(0, m.start() - 8):m.end() + 16][:80]))
    return out


def walk_strings(obj, path=""):
    """Every string in a JSON value, keys included, with a pointer to it."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield path + "/" + str(k), str(k)
            yield from walk_strings(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, "%s/%d" % (path, i))


# ---------------------------------------------------------------- PNG
def png_chunks(data):
    """[(type, payload)] of a PNG, CRC checked. Raises ValueError when the file is not a well-formed PNG."""
    if data[:8] != PNG_SIG:
        raise ValueError("not a PNG file")
    i, out = 8, []
    while i < len(data):
        if i + 12 > len(data):
            raise ValueError("truncated chunk")
        n, t = struct.unpack(">I4s", data[i:i + 8])
        if i + 12 + n > len(data):
            raise ValueError("chunk %s runs past the end of the file" % t.decode("latin-1"))
        payload = data[i + 8:i + 8 + n]
        crc = struct.unpack(">I", data[i + 8 + n:i + 12 + n])[0]
        if zlib.crc32(t + payload) & 0xFFFFFFFF != crc:
            raise ValueError("chunk %s has a wrong checksum" % t.decode("latin-1"))
        out.append((t, payload))
        i += 12 + n
        if t == b"IEND":
            break
    if not out or out[0][0] != b"IHDR" or out[-1][0] != b"IEND":
        raise ValueError("a PNG starts with IHDR and ends with IEND")
    return out


def png_size(data):
    ch = png_chunks(data)
    w, h = struct.unpack(">II", ch[0][1][:8])
    return w, h


def png_text(chunks):
    """[(key, value)] of the text chunks of a PNG."""
    out = []
    for t, p in chunks:
        try:
            if t == b"tEXt":
                k, _, v = p.partition(b"\0")
                out.append((k.decode("latin-1"), v.decode("latin-1")))
            elif t == b"zTXt":
                k, _, rest = p.partition(b"\0")
                out.append((k.decode("latin-1"), zlib.decompress(rest[1:]).decode("latin-1")))
            elif t == b"iTXt":
                k, _, rest = p.partition(b"\0")
                comp, rest = rest[0], rest[2:]
                _lang, _, rest = rest.partition(b"\0")
                _tk, _, txt = rest.partition(b"\0")
                out.append((k.decode("latin-1"), (zlib.decompress(txt) if comp else txt).decode("utf-8", "replace")))
        except (zlib.error, IndexError, ValueError):
            out.append((p[:20].decode("latin-1"), "<unreadable>"))
    return out


def image_metadata_problems(data, strict):
    """[message] for metadata in a PNG or JPEG that could carry personal data or a path. strict (renders): only the chunks in RENDER_CHUNKS
    are allowed. Otherwise text is scanned and EXIF, colour profiles and similar blocks are refused."""
    msgs = []
    if data[:8] == PNG_SIG:
        try:
            ch = png_chunks(data)
        except ValueError as exc:
            return ["unreadable PNG: %s" % exc]
        for t, p in ch:
            name = t.decode("latin-1")
            if strict and t not in RENDER_CHUNKS:
                msgs.append("PNG chunk %s is not allowed in a render" % name)
            elif t in (b"eXIf", b"iCCP"):
                msgs.append("PNG chunk %s (EXIF or colour profile) may hold personal data" % name)
        for k, v in png_text(ch):
            for kind, ex in find_leaks(k + "=" + v):
                msgs.append("PNG text %r holds a %s (%r)" % (k, kind, ex))
            if PERSONAL_KEYS.match(k) and k.lower() != "software" and v.strip():
                msgs.append("PNG text key %r can name a person or place" % k)
        return msgs
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                break
            mk = data[i + 1]
            if mk == 0xDA or mk == 0xD9:
                break
            n = struct.unpack(">H", data[i + 2:i + 4])[0]
            seg = data[i + 4:i + 2 + n]
            if mk == 0xE1:
                msgs.append("JPEG holds an APP1 block (EXIF or XMP)")
            elif mk in (0xED, 0xEE) or mk == 0xFE:
                msgs.append("JPEG holds a %s block (IPTC, Adobe or comment)" % ("COM" if mk == 0xFE else "APP%d" % (mk - 0xE0)))
            elif mk == 0xE2 and seg[:11] == b"ICC_PROFILE":
                msgs.append("JPEG holds a colour profile block")
            for kind, ex in find_leaks(seg.decode("latin-1")):
                msgs.append("JPEG block holds a %s (%r)" % (kind, ex))
            i += 2 + n
        return msgs
    return ["not a PNG or JPEG image"]


# ---------------------------------------------------------------- pictures
def decode_png(data):
    """RGB uint8 array (h, w, 3) of a PNG (alpha dropped)."""
    import io

    import numpy as np
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def compare_pictures(a, b, tol):
    """Compare two decoded pictures. tol: {"meanAbsLevels", "differingFraction", "differenceLevels"}. Returns (ok, stats)."""
    import numpy as np
    if a.shape != b.shape:
        return False, {"reason": "size %s against %s" % (a.shape[:2][::-1], b.shape[:2][::-1])}
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    mean = float(d.mean())
    frac = float((d > tol["differenceLevels"]).mean())
    stats = {"meanAbsLevels": round(mean, 4), "differingFraction": round(frac, 6), "maxLevels": int(d.max())}
    return mean <= tol["meanAbsLevels"] and frac <= tol["differingFraction"], stats


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
