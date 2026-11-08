#!/usr/bin/env python3
"""List or verify members of an ISO-9660 (level 1/2) data track.

usage: iso_verify.py IMAGE --list
       iso_verify.py IMAGE ISO_PATH --equals FILE
Prints size and sha256. Exit 1 when the member differs or is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

SECTOR = 2048


def record(data: bytes, offset: int) -> tuple[int, int, int, str]:
    length = data[offset]
    if length == 0:
        return 0, 0, 0, ""
    r = data[offset:offset + length]
    extent = int.from_bytes(r[2:6], "little")
    size = int.from_bytes(r[10:14], "little")
    flags = r[25]
    raw = r[33:33 + r[32]]
    name = "." if raw == b"\x00" else ".." if raw == b"\x01" else raw.decode("ascii").split(";", 1)[0]
    return extent, size, flags, name


def entries(image: bytes, extent: int, size: int) -> dict[str, tuple[int, int, int]]:
    d = image[extent * SECTOR:extent * SECTOR + size]
    out, off = {}, 0
    while off < len(d):
        if d[off] == 0:
            off = (off // SECTOR + 1) * SECTOR
            continue
        e, s, f, n = record(d, off)
        out[n.upper()] = (e, s, f)
        off += d[off]
    return out


def root(image: bytes) -> tuple[int, int, int]:
    pvd = image[16 * SECTOR:17 * SECTOR]
    if len(pvd) < 190 or pvd[0] != 1 or pvd[1:6] != b"CD001":
        raise ValueError("no ISO-9660 primary volume descriptor")
    e, s, f, _ = record(pvd, 156)
    return e, s, f


def read_path(image: bytes, path: str) -> bytes:
    extent, size, flags = root(image)
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    for i, part in enumerate(parts):
        m = entries(image, extent, size).get(part.upper())
        if m is None:
            raise ValueError(f"not found: {part}")
        extent, size, flags = m
        if i + 1 < len(parts) and not flags & 2:
            raise ValueError(f"not a directory: {part}")
    if flags & 2:
        raise ValueError(f"is a directory: {path}")
    return image[extent * SECTOR:extent * SECTOR + size]


def walk(image: bytes, extent: int, size: int, prefix: str = "") -> list[tuple[str, int, int]]:
    out = []
    for name, (e, s, f) in sorted(entries(image, extent, size).items()):
        if name in (".", ".."):
            continue
        if f & 2:
            out += walk(image, e, s, f"{prefix}{name}/")
        else:
            out.append((prefix + name, e, s))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image", type=pathlib.Path)
    ap.add_argument("iso_path", nargs="?")
    ap.add_argument("--equals", type=pathlib.Path)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)
    img = a.image.read_bytes()
    if a.list:
        e, s, _ = root(img)
        for name, ext, size in walk(img, e, s):
            print(f"{ext:8d} {size:10d} {name}")
        return 0
    if not a.iso_path or not a.equals:
        ap.error("give ISO_PATH and --equals, or --list")
    got = read_path(img, a.iso_path)
    want = a.equals.read_bytes()
    if got != want:
        print(f"{a.iso_path} differs from {a.equals} ({len(got)} versus {len(want)} bytes)")
        return 1
    print(f"verified {a.iso_path}: {len(got)} bytes, sha256={hashlib.sha256(got).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
