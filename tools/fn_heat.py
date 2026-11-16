#!/usr/bin/env python3
"""Per-function heat from a profiling emulator's dumps, for hot code placement (tools/place_plan.py).

Moved from avpsaturn v0.1.0-beta, tools/perf/fn_heat.py (MIT, owner's own code). Changes: the nm tool, the counted CPU classes and the address
window are options, the work is split into functions the tests can call, and the AvP object naming is kept as "object:symbol".

usage: fn_heat.py OUT.json MAP ELF PROF.txt [PROF2.txt ...] [--nm PATH] [--classes 0,2] [--min-addr 0x200000]

Keys are "object:symbol" (c3:f_aa016), because the static helpers every object carries exist once per object. A function's heat is what the master
did in it over the profiled windows: instructions executed ("exec") and instruction cache line fills ("ifill"). The names are layout independent,
so a heat file made on one build places the code of another.
MAP is the link map of a build WITHOUT -ffunction-sections (one .text per object), ELF its image.

Profile format, one record per line (a profiling emulator writes it; the kit does not ship one):
  P  CLASS ADDR COUNT     instructions executed at ADDR on CPU class CLASS
  IF CLASS ADDR COUNT     instruction cache line fills at ADDR
Lines starting with anything else are skipped. Only the classes named by --classes are counted (default 0 and 2: the master's game tick and its
vblank handler; the idle spin after the pass is left out because it runs only while the master has nothing to do).
"""
import argparse
import bisect
import collections
import json
import os
import re
import subprocess
import sys


def object_ranges(map_text):
    """(start, end, object stem) of every .text input section in a GNU ld map. Long section names wrap onto the next line."""
    rng = []
    lines = map_text.splitlines()
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"^ (\.text\S*)\s*$", l)
        m2 = re.match(r"^ (\.text\S*)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(.*)$", l)
        if not m2 and m and i + 1 < len(lines):
            m3 = re.match(r"^\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(.*)$", lines[i + 1])
            if m3:
                a, n, path = int(m3.group(1), 16), int(m3.group(2), 16), m3.group(3)
                if n:
                    rng.append((a, a + n, re.split(r"[\\/]", path.strip())[-1].rsplit(".", 1)[0]))
                i += 2
                continue
        if m2 and int(m2.group(3), 16):
            a, n = int(m2.group(2), 16), int(m2.group(3), 16)
            rng.append((a, a + n, re.split(r"[\\/]", m2.group(4).strip())[-1].rsplit(".", 1)[0]))
        i += 1
    rng.sort()
    return rng


def parse_nm(text):
    """(address, size, name) of the text symbols from `nm -S -n` output."""
    syms = []
    for l in text.splitlines():
        p = l.split()
        if len(p) == 4 and p[2] in "tTwW":
            syms.append((int(p[0], 16), int(p[1], 16), p[3]))
    return syms


def compute_heat(profile_files, rng, syms, classes=(0, 2), min_addr=0x00200000):
    starts = [r[0] for r in rng]
    saddr = [s[0] for s in syms]

    def obj_of(a):
        i = bisect.bisect_right(starts, a) - 1
        return rng[i][2] if i >= 0 and a < rng[i][1] else None

    def func_at(a):
        i = bisect.bisect_right(saddr, a) - 1
        if i < 0:
            return None
        s = syms[i]
        if a >= s[0] + max(s[1], 2) + 64:
            return None
        return i

    heat = collections.defaultdict(lambda: {"exec": 0, "ifill": 0, "size": 0, "scenes": 0})
    for pf in profile_files:
        seen = set()
        lines = pf.splitlines() if isinstance(pf, str) else open(pf)
        for l in lines:
            t = l.split()
            if len(t) < 4 or t[0] not in ("P", "IF"):
                continue
            if int(t[1]) not in classes:
                continue
            a = int(t[2], 16)
            if (a & 0x1FFFFFFF) < min_addr or 0x05000000 <= (a & 0x1FFFFFFF) < 0x06000000:
                continue
            i = func_at(a)
            if i is None:
                continue
            o = obj_of(syms[i][0])
            if o is None:
                continue
            # symbols that share an address (identical split-off bodies) all get the heat: the linker section carries one of the names
            j0 = i
            while j0 > 0 and syms[j0 - 1][0] == syms[i][0]:
                j0 -= 1
            j1 = i
            while j1 + 1 < len(syms) and syms[j1 + 1][0] == syms[i][0]:
                j1 += 1
            for j in range(j0, j1 + 1):
                name = syms[j][2]
                k = f"{o}:{name[1:] if name.startswith('_') else name}"
                h = heat[k]
                h["size"] = syms[j][1]
                h["exec" if t[0] == "P" else "ifill"] += int(t[3])
                if k not in seen:
                    seen.add(k)
                    h["scenes"] += 1
    return dict(heat)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("out")
    ap.add_argument("map")
    ap.add_argument("elf")
    ap.add_argument("profiles", nargs="+")
    ap.add_argument("--nm", default=os.environ.get("NM", "sh-elf-nm"))
    ap.add_argument("--classes", default="0,2")
    ap.add_argument("--min-addr", default="0x200000")
    a = ap.parse_args(argv)
    try:
        nm_out = subprocess.run([a.nm, "-S", "-n", a.elf], capture_output=True, text=True, check=True).stdout
        rng = object_ranges(open(a.map, errors="replace").read())
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"fn_heat: {e}", file=sys.stderr)
        return 2
    heat = compute_heat(a.profiles, rng, parse_nm(nm_out), tuple(int(x) for x in a.classes.split(",")), int(a.min_addr, 0))
    with open(a.out, "w") as f:
        json.dump(heat, f, indent=0, sort_keys=True)
    ex = [k for k, v in heat.items() if v["exec"] > 0]
    print(f"{len(heat)} functions with heat, {len(ex)} executed, {sum(heat[k]['size'] for k in ex)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
