#!/usr/bin/env python3
"""Check and patch the boot fields of a Saturn IP.BIN.

Fields (big endian):
  0x000  "SEGA SEGASATURN " hardware id
  0x0E0  IP size (0x1800 for a stock header with one area code)
  0x0F0  first read load address
  0x0F4  first read size (0 = the first file's own length)
Some headers hold a second copy of the load address further in; --embedded-offset names it (Jo Engine's: 0x1014).

usage: ip_bin.py check IP.BIN
       ip_bin.py patch IP.BIN OUT.BIN --load 0x06004000 [--read-size 0] [--embedded-offset 0x1014]
                       [--expect-size 0x1800] [--config C]
Patching refuses headers with an unexpected size, or where the old load address appears anywhere other than the
fields being patched. The output is read back and checked.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

HWID = b"SEGA SEGASATURN "
SIZE_OFF, LOAD_OFF, READ_OFF = 0xE0, 0xF0, 0xF4


def be32(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "big")


def fields(b: bytes) -> dict:
    if len(b) < 0xF8:
        raise ValueError("too short for Saturn boot fields")
    return dict(hwid_ok=b[:16] == HWID, size=be32(b, SIZE_OFF), load=be32(b, LOAD_OFF), read=be32(b, READ_OFF))


def patch(src: bytes, load: int, read_size: int, embedded: int | None, expect_size: int) -> bytes:
    f = fields(src)
    if f["size"] != expect_size:
        raise ValueError(f"IP size {f['size']:#x}, expected {expect_size:#x}")
    old = f["load"].to_bytes(4, "big")
    targets = [LOAD_OFF] + ([embedded] if embedded is not None else [])
    for t in targets[1:]:
        if src[t:t + 4] != old:
            raise ValueError(f"embedded load address at {t:#x} does not match the header's")
    found = [i for i in range(len(src) - 3) if src[i:i + 4] == old]
    if found != sorted(targets):
        raise ValueError("load address appears at unexpected offsets: " + ",".join(f"{x:#x}" for x in found))
    out = bytearray(src)
    for t in targets:
        out[t:t + 4] = load.to_bytes(4, "big")
    out[READ_OFF:READ_OFF + 4] = read_size.to_bytes(4, "big")
    g = fields(bytes(out))
    if g["load"] != load or g["read"] != read_size or any(be32(out, t) != load for t in targets):
        raise ValueError("read-back check failed")
    return bytes(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "patch"])
    ap.add_argument("ip", type=pathlib.Path)
    ap.add_argument("out", nargs="?", type=pathlib.Path)
    ap.add_argument("--load", type=lambda s: int(s, 0))
    ap.add_argument("--read-size", type=lambda s: int(s, 0))
    ap.add_argument("--embedded-offset", type=lambda s: int(s, 0))
    ap.add_argument("--expect-size", type=lambda s: int(s, 0), default=0x1800)
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    src = a.ip.read_bytes()
    if a.cmd == "check":
        f = fields(src)
        print(f"hwid {'ok' if f['hwid_ok'] else 'MISSING'} size {f['size']:#x} load {f['load']:#010x} read {f['read']}")
        return 0 if f["hwid_ok"] else 1
    load, rs = a.load, a.read_size
    if a.config:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        import cfg
        c = cfg.load(a.config)
        load = load if load is not None else cfg.get(c, "saturn.ip_load_address")
        rs = rs if rs is not None else cfg.get(c, "saturn.ip_read_size")
    if load is None or a.out is None:
        ap.error("patch needs OUT and --load (or a config)")
    out = patch(src, load, rs or 0, a.embedded_offset, a.expect_size)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(out)
    print(f"IP.BIN: {len(out)} bytes, load {load:#010x}, read {rs or 0}, sha256 {hashlib.sha256(out).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
