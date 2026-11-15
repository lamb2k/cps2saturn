#!/usr/bin/env python3
"""Data alignment gate for SH-2 builds. Stdlib only, no toolchain needed to run it on saved nm output.

The lesson: an SH-2 raises an address error on a 16-bit access at an odd address and on a 32-bit access at an address
that is not a multiple of 4. Emulators allow both. A table of bytes that sat at 2 mod 4 and was read through a 32-bit
pointer ran fine in an emulator and killed a CPU on a real console. This gate finds those before a disc is burned.
Checks:
  symbols   every data symbol in nm output (types D d R r B b C c G g S s V v W w) must be aligned to what its size
            implies: size a multiple of 4 -> 4, a multiple of 2 -> 2. Byte-only data that really is read byte by byte
            is listed in an allowlist file with the reason. --must-align NAME=N forces a symbol to N (the base of a
            table that code reads as longs must be 4 aligned whatever its size).
  offsets   in C sources (--src DIR), a literal byte offset added to the pointer argument of a listed wide accessor
            (--accessor NAME:WIDTH, e.g. get32:4) must be a multiple of its width: get32(p + 6) is wrong whatever p is.
  sites     in C sources, every cast of a non-literal pointer to a 16/32-bit pointer type must be on a reviewed list
            (--sites FILE). A new or edited site fails until someone reviews it. This finds WHO reads byte data as words,
            which the symbol check cannot. Literal hardware addresses and the address of a typed object are skipped.
Files:
  nm input   `nm -S -n` style lines: ADDRESS SIZE TYPE NAME (--nm-file), or run a tool on ELF files (--nm TOOL --elf ELF).
  allowlist  lines `NAME reason` (# comments allowed).
  sites      lines `KEY reason`, KEY as printed by --list-sites (file plus a hash of the normalised line).
usage: align_gate.py (--nm-file FILE | --nm TOOL --elf ELF [--elf ...]) [--allow FILE] [--must-align NAME=N ...]
                     [--src DIR [--accessor NAME:WIDTH ...] [--sites FILE | --list-sites]] [--report FILE]
Exit 0 clean, 1 any hit, 2 bad input.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import subprocess
import sys

DATA_TYPES = set("DdRrBbCcGgSsVvWw")
SRC_SUFFIXES = {".c", ".h", ".inc"}


class BadInput(Exception):
    pass


def parse_nm(text: str) -> list[tuple[int, int, str, str]]:
    """Lines `addr size type name` (hex addr and size) -> [(addr, size, type, name)]. Other lines are ignored."""
    syms = []
    for line in text.splitlines():
        p = line.split()
        if len(p) == 4 and len(p[2]) == 1:
            try:
                syms.append((int(p[0], 16), int(p[1], 16), p[2], p[3].lstrip("_")))
            except ValueError:
                continue
    return syms


def run_nm(tool: str, elf: str) -> str:
    try:
        r = subprocess.run([tool, "-S", "-n", elf], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        raise BadInput(f"cannot run {tool} on {elf}: {e}")
    return r.stdout


def load_list(path: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if path:
        p = pathlib.Path(path)
        if not p.exists():
            raise BadInput(f"no such file: {path}")
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Site keys are "<file> <10-hex hash>" (as --list-sites prints them), so the key holds one space.
                m = re.match(r"^(.*? [0-9a-f]{10})(?:\s+(.*))?$", line)
                if m:
                    out[m.group(1)] = (m.group(2) or "").strip()
                else:
                    key, _, why = line.partition(" ")
                    out[key] = why.strip()
    return out


def required_alignment(size: int) -> int:
    return 4 if size % 4 == 0 else 2 if size % 2 == 0 else 1


def check_symbols(syms, allow: dict[str, str], must: dict[str, int], hits: list[str]) -> int:
    n, seen = 0, set()
    for addr, size, typ, name in syms:
        if name in must and addr % must[name]:
            hits.append(f"symbol {name} at 0x{addr:08x}: must be {must[name]} aligned, is {addr % must[name]} mod {must[name]}")
        if typ not in DATA_TYPES or size == 0 or (name, addr) in seen:
            continue
        seen.add((name, addr))
        n += 1
        need = required_alignment(size)
        if addr % need and name not in allow:
            hits.append(f"symbol {name} at 0x{addr:08x} size {size}: needs {need} byte alignment, is {addr % need} mod {need} "
                        f"(align it, or allow it with a reason if it is only ever read as bytes)")
    return n


def source_files(root: pathlib.Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in SRC_SUFFIXES:
            yield path


# ---- offsets ----

def first_arg(code: str, i: int) -> str:
    depth, j = 0, i
    while j < len(code):
        c = code[j]
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        j += 1
    return code[i:j]


def check_offsets(src: pathlib.Path, accessors: dict[str, int], hits: list[str]) -> int:
    if not accessors:
        return 0
    call = re.compile(r"\b(" + "|".join(map(re.escape, accessors)) + r")\s*\(")
    n = 0
    for path in source_files(src):
        rel = path.relative_to(src).as_posix()
        for ln, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            code = line.split("//", 1)[0]
            for m in call.finditer(code):
                full = first_arg(code, m.end())
                n += 1
                flat = full
                while True:   # terms inside a nested parenthesis belong to a product or a cast, not to the byte offset
                    g = re.sub(r"\([^()]*\)", "()", flat)
                    if g == flat:
                        break
                    flat = g
                width = accessors[m.group(1)]
                for t in re.finditer(r"\+\s*(0x[0-9a-fA-F]+|\d+)\b(?!\s*[*/<(])", flat):
                    v = int(t.group(1), 0)
                    if v % width:
                        hits.append(f"offset {rel}:{ln}: {m.group(1)}({full.strip()}) adds {v}, not a multiple of {width}")
    return n


# ---- cast sites ----

WIDE_TYPES = (r"u16|u32|s16|s32|unsigned\s+short|unsigned\s+long|unsigned\s+int|uint16_t|uint32_t|int16_t|int32_t|"
              r"short|int|long")
CAST = re.compile(r"\(\s*(?:const\s+)?(?:volatile\s+)?(?:" + WIDE_TYPES + r")\s*\*\s*\)")


def site_lines(src: pathlib.Path, extra_types: tuple[str, ...] = ()):
    """(relpath, line number, line text, key) of every non-literal cast to a 16/32-bit pointer."""
    cast = CAST
    if extra_types:
        cast = re.compile(r"\(\s*(?:const\s+)?(?:volatile\s+)?(?:" + WIDE_TYPES + "|" + "|".join(map(re.escape, extra_types)) + r")\s*\*\s*\)")
    out = []
    for path in source_files(src):
        rel = path.relative_to(src).as_posix()
        for ln, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
            code = line.split("//", 1)[0]
            hit = False
            for m in cast.finditer(code):
                rest = code[m.end():]
                if re.match(r"\s*\(?\s*(?:\(void\s*\*\)\s*)?\(?\s*0x[0-9a-fA-F]+", rest):   # a hardware or fixed RAM address
                    continue
                if re.match(r"\s*&\s*[\w(]", rest):   # the address of a typed object
                    continue
                hit = True
            if hit:
                norm = " ".join(code.split())
                out.append((rel, ln, line.strip(), rel + " " + hashlib.sha1(norm.encode()).hexdigest()[:10]))
    return out


def check_sites(src: pathlib.Path, reviewed: dict[str, str], hits: list[str], list_only=False, extra_types=()) -> int:
    found = site_lines(src, tuple(extra_types))
    keys = set()
    for rel, ln, text, key in found:
        keys.add(key)
        if list_only:
            print(f"{key}  # {ln}: {text[:110]}")
        elif not reviewed.get(key):
            hits.append(f"site {rel}:{ln}: {text[:140]}  (16/32-bit access through a cast pointer that is not reviewed: "
                        f"make the source aligned or a byte path, then add `{key} reason` to the sites list)")
    if not list_only:
        for key in reviewed:
            if key not in keys:
                print(f"  note: reviewed site {key} no longer exists (stale entry)")
    return len(found)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SH-2 data alignment gate")
    ap.add_argument("--nm-file", help="saved `nm -S -n` output")
    ap.add_argument("--nm", help="nm tool to run on each --elf")
    ap.add_argument("--elf", action="append", default=[])
    ap.add_argument("--allow", help="byte-only data allowlist (NAME reason)")
    ap.add_argument("--must-align", action="append", default=[], metavar="NAME=N")
    ap.add_argument("--src", help="C source folder for the offset and site checks")
    ap.add_argument("--accessor", action="append", default=[], metavar="NAME:WIDTH")
    ap.add_argument("--cast-type", action="append", default=[], help="extra wide type name for the site scan")
    ap.add_argument("--sites", help="reviewed cast-site list (KEY reason)")
    ap.add_argument("--list-sites", action="store_true", help="print site keys and exit")
    ap.add_argument("--report")
    a = ap.parse_args(argv)
    hits: list[str] = []
    try:
        text = ""
        if a.nm_file:
            p = pathlib.Path(a.nm_file)
            if not p.exists():
                raise BadInput(f"no such file: {a.nm_file}")
            text = p.read_text(errors="replace")
        elif a.nm and a.elf:
            text = "\n".join(run_nm(a.nm, e) for e in a.elf)
        syms = parse_nm(text) if text else []
        if (a.nm_file or a.elf) and not syms:
            raise BadInput("no symbols found in the nm input")
        if not (syms or a.src):
            raise BadInput("give --nm-file or --nm/--elf, and/or --src")
        if a.src and not (a.accessor or a.sites is not None or a.list_sites) and not syms:
            raise BadInput("--src needs --accessor and/or --sites")
        must = {}
        for m in a.must_align:
            k, _, v = m.partition("=")
            if not v.isdigit():
                raise BadInput(f"--must-align wants NAME=N, got {m!r}")
            must[k] = int(v)
        accessors = {}
        for s in a.accessor:
            k, _, v = s.partition(":")
            if not v.isdigit() or int(v) not in (2, 4):
                raise BadInput(f"--accessor wants NAME:2 or NAME:4, got {s!r}")
            accessors[k] = int(v)
        src = pathlib.Path(a.src) if a.src else None
        if src is not None and not src.is_dir():
            raise BadInput(f"no such folder: {a.src}")
        if a.list_sites:
            if src is None:
                raise BadInput("--list-sites needs --src")
            check_sites(src, {}, hits, list_only=True, extra_types=a.cast_type)
            return 0
        nsym = check_symbols(syms, load_list(a.allow), must, hits)
        nsite = noff = 0
        if src is not None:
            noff = check_offsets(src, accessors, hits)
            if a.sites is not None:
                nsite = check_sites(src, load_list(a.sites), hits, extra_types=a.cast_type)
    except BadInput as e:
        print("bad input:", e, file=sys.stderr)
        return 2
    msg = f"align gate: {nsym} data symbols, {nsite} cast sites, {noff} accessor calls, {len(hits)} hits"
    print(msg)
    for h in hits:
        print("  HIT", h)
    if a.report:
        pathlib.Path(a.report).write_text(msg + "\n" + "\n".join(hits) + "\n")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
