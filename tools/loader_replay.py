#!/usr/bin/env python3
"""Offline replay of a loader's read plan: plain sequential loading against a coalesced plan, with checksums.

The lesson: loaders merge many small reads into one big read into a staging area, then copy the pieces to their real
destinations. If the staging area overlaps memory that was already loaded, or a destination, the merge silently
corrupts it, and it does so on only some files. Replaying the plan on the host, over every file, and comparing the final
memory of every region against plain sequential loading finds it without a console. Second lesson, about the check
itself: a rotating-xor checksum cancels where regions overlap (every overlapped word is folded in twice with the same
rotation, so whatever it holds, right or corrupt, adds nothing), so it can pass a plan that is broken exactly there.
A multiplicative checksum (a chain of multiply-and-add) does not cancel, and sees it.

Plan file (JSON):
  memory_size   bytes of the modelled memory (default 0x400000)
  base          address of the first byte of the model (default 0)
  stage         address of the staging area used by coalesced groups
  regions       list of {file, offset, length, dest}, in load order; file is relative to --root (default: the plan's folder)
  groups        optional list of lists of region indices read as one span (min offset to max end, one file, in order);
                regions in no group load alone. Without it, --auto-group merges neighbouring regions of one file that are
                contiguous in that file.
Output: reads sequential vs coalesced, each region whose final memory differs, and both checksums over the regions for
both memories. Exit 0 when every region matches, 1 when any differs (or, with --judge mul|xor, when that checksum differs),
2 bad input.
usage: loader_replay.py PLAN.json [--root DIR] [--auto-group] [--max-group-bytes N] [--judge bytes|mul|xor]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

MASK = 0xFFFFFFFF


class BadInput(Exception):
    pass


def words(data: bytes):
    for i in range(0, len(data), 4):
        yield int.from_bytes(data[i:i + 4].ljust(4, b"\0"), "big")


def rotl(v: int, k: int) -> int:
    k %= 32
    return ((v << k) | (v >> (32 - k))) & MASK if k else v


def checksum(mem, base: int, regions, algo: str) -> int:
    """Checksum over the memory range of each region in list order (a word covered by two regions is folded in twice).
    xor: rotating xor, rotation by the word's address. mul: multiply by a constant and add the word and its address."""
    acc = 0
    for r in regions:
        lo = r["dest"] - base
        for n, w in enumerate(words(bytes(mem[lo:lo + r["length"]]))):
            addr_word = (r["dest"] + 4 * n) >> 2
            if algo == "xor":
                acc ^= rotl(w, addr_word)
            elif algo == "mul":
                acc = (acc * 0x01000193 + w + addr_word) & MASK
            else:
                raise ValueError(algo)
    return acc


def load_plan(path: pathlib.Path, root: pathlib.Path | None):
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BadInput(f"cannot read plan {path}: {e}")
    root = root or path.parent
    regions = plan.get("regions")
    if not isinstance(regions, list) or not regions:
        raise BadInput("plan has no regions")
    data = {}
    for n, r in enumerate(regions):
        try:
            r["offset"], r["length"], r["dest"] = int(r["offset"]), int(r["length"]), int(r["dest"])
            name = r["file"]
        except (KeyError, TypeError, ValueError):
            raise BadInput(f"region {n}: needs file, offset, length, dest")
        if name not in data:
            fp = root / name
            if not fp.is_file():
                raise BadInput(f"region {n}: no such file {fp}")
            data[name] = fp.read_bytes()
        if r["offset"] < 0 or r["length"] <= 0 or r["offset"] + r["length"] > len(data[name]):
            raise BadInput(f"region {n}: reads past the end of {name}")
    return plan, data


def auto_groups(regions, max_bytes: int):
    groups, cur = [], [0]
    for i in range(1, len(regions)):
        p, r = regions[cur[-1]], regions[i]
        span = r["offset"] + r["length"] - regions[cur[0]]["offset"]
        if r["file"] == p["file"] and r["offset"] == p["offset"] + p["length"] and span <= max_bytes:
            cur.append(i)
        else:
            groups.append(cur)
            cur = [i]
    groups.append(cur)
    return [g for g in groups if len(g) > 1]


def write(mem, base: int, addr: int, buf: bytes, what: str):
    lo = addr - base
    if lo < 0 or lo + len(buf) > len(mem):
        raise BadInput(f"{what}: write of {len(buf)} bytes at 0x{addr:x} is outside the modelled memory")
    mem[lo:lo + len(buf)] = buf


def replay(plan, data, groups=None):
    """Returns (sequential memory, coalesced memory, reads sequential, reads coalesced)."""
    base = int(plan.get("base", 0))
    size = int(plan.get("memory_size", 0x400000))
    regions = plan["regions"]
    piece = lambda r: data[r["file"]][r["offset"]:r["offset"] + r["length"]]
    ref = bytearray(size)
    for n, r in enumerate(regions):
        write(ref, base, r["dest"], piece(r), f"region {n}")
    groups = groups if groups is not None else plan.get("groups") or []
    first = {g[0]: g for g in groups}
    member = {i for g in groups for i in g}
    mem, reads, i = bytearray(size), 0, 0
    if groups and "stage" not in plan:
        raise BadInput("groups need a stage address")
    stage = int(plan.get("stage", 0))
    for i in range(len(regions)):
        if i in first:
            g = first[i]
            rs = [regions[k] for k in g]
            if len({r["file"] for r in rs}) != 1:
                raise BadInput(f"group {g}: regions come from different files")
            lo = min(r["offset"] for r in rs)
            hi = max(r["offset"] + r["length"] for r in rs)
            write(mem, base, stage, data[rs[0]["file"]][lo:hi], f"stage of group {g}")
            reads += 1
            for r in rs:
                s = stage - base + (r["offset"] - lo)
                write(mem, base, r["dest"], bytes(mem[s:s + r["length"]]), f"group {g}")
        elif i not in member:
            write(mem, base, regions[i]["dest"], piece(regions[i]), f"region {i}")
            reads += 1
    return ref, mem, len(regions), reads


def compare(plan, ref, mem):
    base = int(plan.get("base", 0))
    bad = [n for n, r in enumerate(plan["regions"])
           if ref[r["dest"] - base:r["dest"] - base + r["length"]] != mem[r["dest"] - base:r["dest"] - base + r["length"]]]
    sums = {a: (checksum(ref, base, plan["regions"], a), checksum(mem, base, plan["regions"], a)) for a in ("xor", "mul")}
    return bad, sums


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="replay a loader read plan, sequential vs coalesced")
    ap.add_argument("plan")
    ap.add_argument("--root", type=pathlib.Path)
    ap.add_argument("--auto-group", action="store_true")
    ap.add_argument("--max-group-bytes", type=int, default=1 << 20)
    ap.add_argument("--judge", choices=("bytes", "mul", "xor"), default="bytes")
    a = ap.parse_args(argv)
    try:
        plan, data = load_plan(pathlib.Path(a.plan), a.root)
        groups = auto_groups(plan["regions"], a.max_group_bytes) if a.auto_group and not plan.get("groups") else None
        ref, mem, rs, rc = replay(plan, data, groups)
    except BadInput as e:
        print("bad input:", e, file=sys.stderr)
        return 2
    bad, sums = compare(plan, ref, mem)
    print(f"reads: {rs} sequential, {rc} coalesced; {len(bad)} of {rs} regions differ from sequential loading"
          + (f": {bad[:20]}" if bad else ""))
    for algo, (x, y) in sums.items():
        print(f"checksum {algo}: sequential {x:08x}, coalesced {y:08x} -> {'same' if x == y else 'DIFFERENT'}")
    if a.judge == "bytes":
        failed = bool(bad)
    else:
        failed = sums[a.judge][0] != sums[a.judge][1]
    print("loader_replay:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
