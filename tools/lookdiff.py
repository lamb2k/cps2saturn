#!/usr/bin/env python3
"""Pixel diff of two screenshots (or two folders of them): changed-pixel share, bounding box, optional diff image.

The lesson: after a performance or memory change, "it looks the same" is a claim to measure. Capture the same frame
from the old and the new build (same game tick, same capture size), compare, and read the share of pixels that moved
and where. Mask the parts that legitimately differ (a build id, a frame counter, a blinking prompt) so they do not
hide a real change, and set a limit so the check is a gate instead of an opinion.
Stdlib only: reads and writes 8-bit non-interlaced PNG itself (grey, grey+alpha, RGB, RGBA, palette). Pillow, when
installed, is used for any other format or PNG flavour; without it those inputs exit 2.

usage: lookdiff.py A B [--out FILE_OR_DIR] [--threshold 24] [--crop X0,Y0,X1,Y1] [--mask X0,Y0,X1,Y1 ...] [--max-pct 0]
  A and B are two image files, or two folders (files with the same name are compared).
  threshold  a pixel counts as changed when any colour channel differs by more than this (0..255)
  crop       compare only this box; mask  ignore this box (repeatable); boxes are in pixels, X1/Y1 exclusive
  out        diff image written as A | B | difference (red on black); for folders, a folder
  max-pct    pass when every compared pair changes at most this share of its pixels (default 0: any change fails)
Exit 0 pass, 1 over the limit (or a size mismatch), 2 bad input.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"


class BadInput(Exception):
    pass


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def read_png(path):
    """-> (width, height, rgb bytes). Stdlib decoder for 8-bit non-interlaced PNG."""
    data = pathlib.Path(path).read_bytes()
    if data[:8] != PNG_SIG:
        raise BadInput("not a PNG")
    pos, idat, plte, ihdr = 8, [], None, None
    while pos + 8 <= len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            plte = body
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if not ihdr or not idat:
        raise BadInput("truncated PNG")
    w, h, depth, ctype, _, _, interlace = ihdr
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if depth != 8 or interlace or chans is None or (ctype == 3 and not plte):
        raise BadInput("unsupported PNG flavour")
    raw = zlib.decompress(b"".join(idat))
    stride = w * chans
    if len(raw) < h * (stride + 1):
        raise BadInput("truncated PNG data")
    out, prev = bytearray(), bytearray(stride)
    for y in range(h):
        ft = raw[y * (stride + 1)]
        row = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if ft == 1:
            for i in range(chans, stride):
                row[i] = (row[i] + row[i - chans]) & 255
        elif ft == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                left = row[i - chans] if i >= chans else 0
                row[i] = (row[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                left = row[i - chans] if i >= chans else 0
                ul = prev[i - chans] if i >= chans else 0
                row[i] = (row[i] + _paeth(left, prev[i], ul)) & 255
        elif ft != 0:
            raise BadInput("bad PNG filter")
        prev = row
        if ctype == 2:
            out += row
        elif ctype == 6:
            for i in range(0, stride, 4):
                out += row[i:i + 3]
        elif ctype == 0:
            for v in row:
                out += bytes((v, v, v))
        elif ctype == 4:
            for i in range(0, stride, 2):
                out += bytes((row[i],) * 3)
        else:
            for v in row:
                out += plte[3 * v:3 * v + 3]
    return w, h, bytes(out)


def write_png(path, w, h, rgb):
    raw = b"".join(b"\0" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    pathlib.Path(path).write_bytes(PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                                   + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def load_image(path):
    try:
        return read_png(path)
    except (BadInput, zlib.error, struct.error, OSError) as first:
        try:
            from PIL import Image   # optional
        except ImportError:
            raise BadInput(f"{path}: {first} (Pillow is not installed for other formats)")
        try:
            im = Image.open(path).convert("RGB")
        except Exception as e:   # noqa: BLE001 - any decode failure is bad input
            raise BadInput(f"{path}: {e}")
        return im.size[0], im.size[1], im.tobytes()


def parse_box(s):
    try:
        x0, y0, x1, y1 = (int(v) for v in s.split(","))
    except ValueError:
        raise BadInput(f"box {s!r}: want X0,Y0,X1,Y1")
    if x1 <= x0 or y1 <= y0:
        raise BadInput(f"box {s!r} is empty")
    return x0, y0, x1, y1


def diff(a, b, threshold=24, crop=None, masks=()):
    """a, b = (w, h, rgb). Returns dict(changed, total, pct, bbox, mask) where mask is bytes of 0/1 per pixel over the crop box."""
    (w, h, pa), (w2, h2, pb) = a, b
    if (w, h) != (w2, h2):
        raise ValueError(f"size differs: {w}x{h} against {w2}x{h2}")
    x0, y0, x1, y1 = crop or (0, 0, w, h)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        raise BadInput("crop box is outside the image")
    cw, ch = x1 - x0, y1 - y0
    mask = bytearray(cw * ch)
    changed = 0
    bx0, by0, bx1, by1 = cw, ch, -1, -1
    ign = [(max(m[0], x0) - x0, max(m[1], y0) - y0, min(m[2], x1) - x0, min(m[3], y1) - y0) for m in masks]
    for y in range(ch):
        base = ((y + y0) * w + x0) * 3
        ra, rb = pa[base:base + cw * 3], pb[base:base + cw * 3]
        if ra == rb:
            continue
        for x in range(cw):
            i = 3 * x
            if ra[i:i + 3] == rb[i:i + 3]:
                continue
            if max(abs(ra[i] - rb[i]), abs(ra[i + 1] - rb[i + 1]), abs(ra[i + 2] - rb[i + 2])) <= threshold:
                continue
            if any(m[0] <= x < m[2] and m[1] <= y < m[3] for m in ign):
                continue
            mask[y * cw + x] = 1
            changed += 1
            bx0, by0, bx1, by1 = min(bx0, x), min(by0, y), max(bx1, x), max(by1, y)
    bbox = (x0 + bx0, y0 + by0, x0 + bx1 + 1, y0 + by1 + 1) if changed else None
    return dict(changed=changed, total=cw * ch, pct=100.0 * changed / (cw * ch), bbox=bbox, mask=bytes(mask), box=(x0, y0, x1, y1))


def diff_image(a, b, r):
    (w, h, pa), (_, _, pb) = a, b
    x0, y0, x1, y1 = r["box"]
    cw, ch = x1 - x0, y1 - y0
    rows = []
    for y in range(ch):
        base = ((y + y0) * w + x0) * 3
        red = b"".join(b"\xff\0\0" if r["mask"][y * cw + x] else b"\0\0\0" for x in range(cw))
        rows.append(pa[base:base + cw * 3] + pb[base:base + cw * 3] + red)
    return cw * 3, ch, b"".join(rows)


def pairs(a: pathlib.Path, b: pathlib.Path):
    if a.is_dir() and b.is_dir():
        names = sorted(p.name for p in a.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".bmp", ".jpg", ".jpeg"))
        if not names:
            raise BadInput(f"no images in {a}")
        return [(n, a / n, b / n) for n in names]
    if a.is_file() and b.is_file():
        return [(a.name, a, b)]
    raise BadInput("give two files or two folders")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="pixel diff of two screenshots")
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--out")
    ap.add_argument("--threshold", type=int, default=24)
    ap.add_argument("--crop")
    ap.add_argument("--mask", action="append", default=[])
    ap.add_argument("--max-pct", type=float, default=0.0)
    a = ap.parse_args(argv)
    try:
        if not 0 <= a.threshold <= 255:
            raise BadInput("threshold is 0..255")
        crop = parse_box(a.crop) if a.crop else None
        masks = [parse_box(m) for m in a.mask]
        todo = pairs(pathlib.Path(a.a), pathlib.Path(a.b))
        worst, failed = 0.0, False
        for name, pa, pb in todo:
            ia, ib = load_image(pa), load_image(pb)
            try:
                r = diff(ia, ib, a.threshold, crop, masks)
            except ValueError as e:
                print(f"{name}: {e}")
                failed = True
                continue
            worst = max(worst, r["pct"])
            print(f"{name}: {r['changed']} of {r['total']} pixels differ ({r['pct']:.3f} %) bbox {r['bbox']}")
            if a.out:
                dest = pathlib.Path(a.out)
                if len(todo) > 1 or dest.is_dir() or dest.suffix == "":
                    os.makedirs(dest, exist_ok=True)
                    dest = dest / f"diff_{pathlib.Path(name).stem}.png"
                write_png(dest, *diff_image(ia, ib, r))
    except (BadInput, OSError) as e:
        print("bad input:", e, file=sys.stderr)
        return 2
    ok = not failed and worst <= a.max_pct
    print(f"lookdiff: worst {worst:.3f} % against limit {a.max_pct} % -> {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
