#!/usr/bin/env python3
"""Bounded 68000 disassembly and cross references over a decrypted opcode image. Needs capstone.

usage:
  dis68k.py OPCODES.bin vectors [--program PROGRAM.bin]
  dis68k.py OPCODES.bin range START END [START END ...]
  dis68k.py OPCODES.bin xref ADDR [ADDR ...]     absolute long and short references
Addresses are hex. Prints derived text to stdout only; do not commit its output.

CPS2 note: opcode fetches and PC-relative reads come from the opcode view; absolute data reads from the program
view. Read vectors from the program view when you have it.
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys


def disassembler():
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000 | capstone.CS_MODE_BIG_ENDIAN)
    md.skipdata = True
    return md


def dis(op: bytes, start: int, end: int, md=None) -> list[str]:
    md = md or disassembler()
    return [f"{i.address:06x}: {i.bytes.hex():<20} {i.mnemonic} {i.op_str}".rstrip() for i in md.disasm(op[start:end], start)]


def vectors(image: bytes) -> list[str]:
    out = []
    for n in list(range(0, 8)) + list(range(24, 40)):
        out.append(f"vec {n:2d} @{n * 4:03x}: {struct.unpack_from('>I', image, n * 4)[0]:08x}")
    return out


def xref(op: bytes, addr: int, md=None, short_min: int = 0xFF8000) -> list[str]:
    md = md or disassembler()
    pats = [struct.pack(">I", addr)]
    if addr >= short_min:
        pats.append(struct.pack(">H", addr & 0xFFFF))
    out = []
    for pat in pats:
        pos = 0
        while (pos := op.find(pat, pos)) >= 0:
            if pos % 2 == 0:
                for back in (2, 4, 6):
                    if pos - back < 0:
                        continue
                    insns = list(md.disasm(op[pos - back:pos + 8], pos - back, 1))
                    if insns and insns[0].size >= back + len(pat) and f"{addr:x}" in insns[0].op_str:
                        out.append(f"{insns[0].address:06x}: {insns[0].mnemonic} {insns[0].op_str}")
                        break
            pos += 2
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("opcodes", type=pathlib.Path)
    ap.add_argument("cmd", choices=["vectors", "range", "xref"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--program", type=pathlib.Path)
    a = ap.parse_args(argv)
    op = a.opcodes.read_bytes()
    if a.cmd == "vectors":
        print("\n".join(vectors(a.program.read_bytes() if a.program else op)))
    elif a.cmd == "range":
        v = [int(x, 16) for x in a.args]
        for s, e in zip(v[::2], v[1::2]):
            print(f"--- {s:06x}..{e:06x}")
            print("\n".join(dis(op, s, e)))
    else:
        for x in a.args:
            print("== xref", x)
            print("\n".join(xref(op, int(x, 16))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
