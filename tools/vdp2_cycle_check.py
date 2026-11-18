#!/usr/bin/env python3
"""VDP2 VRAM access-cycle rule checker (Saturn). Build gate for the cycle-pattern registers.

The lesson: the VDP2 only draws a scroll layer if the VRAM access cycle pattern gives it enough reads in the right
banks at the right timings. Emulators are lenient about a wrong pattern and real hardware is not, so a pattern that
"works in the emulator" can show garbage or nothing on a console. These rules come from Sega's VDP2 manual (the
tables on pattern name reads, character pattern reads and legal timings) and are checked before anything is burned
to disc. Rules, per enabled NBG layer:
  - pattern name reads per cycle: 1 at 1x, 2 at 1/2 reduction, 4 at 1/4, counted in each bank that holds the
    layer's map (a bitmap layer has no names);
  - cell reads per cycle by colour depth: 16 colours 1/2/4, 256 colours 2/4, 2048 and 32768 colours 4, 16.7 M
    colours 8 (at 1x, 1/2, 1/4; blank means not allowed), counted in each bank that holds the layer's cells;
  - each cell read timing must be legal for the layer's name read timing (NBG0/NBG1 names at T0 are unrestricted);
  - a split bank pair (RAMCTL bit 8 for A, bit 9 for B) needs its CPU access slot in both banks at the same
    timing, with a no-access slot in front of every CPU run;
  - pattern name reads may sit in at most one of A0/B0 and one of A1/B1.
Short counts, illegal timings and broken CPU pairs are errors (exit 1). Extra reads and no CPU slot at all are warnings.
This is a regression rule set, not a model of what the console does when a rule is broken.

usage:
  vdp2_cycle_check.py SPEC.json|SPEC.yaml            check one pattern given in a spec file
  vdp2_cycle_check.py --trace TRACE SPEC             replay a register-write trace and judge every burst
  vdp2_cycle_check.py --cyc A0L,A0U,A1L,A1U,B0L,B0U,B1L,B1U SPEC   override the spec's eight cycle words (hex)
Spec keys (see tests/test_vdp2_cycle_check.py for a worked one): cycles (8 words), ramctl or split_a/split_b,
layers.nbg0..nbg3 {colours, reduction, bitmap, map_banks, cell_banks}, profiles (name -> list of enabled layers),
vertical_cell_scroll_ok. A missing map_banks or cell_banks means "the banks where that layer has reads".
Trace: one register write per line, the last two fields are the register address (offset, or 25F8xxxx) and the value, both
hex; lines starting with # are skipped, any other line ends a burst. The state is judged at the end of each burst while the
display is on and a layer is enabled. Exit 0 pass, 1 rule broken, 2 bad input.

Writer scan (a static check of the SOURCE, no spec needed):
  vdp2_cycle_check.py --scan-writers SRCDIR [--allow FILE] [--writer NAME ...] [--skip-ifdef NAME ...] [--ok-pattern REGEX]
Every write in the C sources under SRCDIR to a register the rules cover (RAMCTL, the eight cycle words, CHCTLA/B, the pattern name and map
registers, PLSZ, ZMCTL) at a literal offset must take its value from the game's layout macros (--ok-pattern, default names starting SAT_V2_
or SAT_CYC_), or be listed in the allowlist with a reason. Why: the rules above judge one set of words, and a second place that writes those
registers with its own numbers (a diagnostic screen, a mode that rewrites the cycles, a reveal screen) is never judged. A new writer fails until
someone reviews it. The writers it looks for are `NAME(0xOFF) = value;` and `NAME([object,] 0xOFF, value);` for each --writer (default SAT_VDP2_REG and
sat_v2l_write). Lines inside `#ifdef NAME` blocks listed with --skip-ifdef (a build that never ships) are skipped. Writes at computed offsets
are not seen: the trace replay (--trace) covers those on a real run. Used with a spec, both run and either failing fails the exit code.
Allowlist lines: `file | substring of the line | reason` (# comments; all three parts required). An entry that matches nothing is reported as stale.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

import cfg

BANKS = ["A0", "A1", "B0", "B1"]
BANK_BASE = {"A0": 0x00000, "A1": 0x20000, "B0": 0x40000, "B1": 0x60000}
# Legal cell read timings for each name read timing (normal resolution).
LEGAL = {0: {0, 1, 2, 4, 5, 6, 7}, 1: {0, 1, 2, 3, 5, 6, 7}, 2: {0, 1, 2, 3, 6, 7}, 3: {0, 1, 2, 3, 7},
         4: {0, 1, 2, 3}, 5: {1, 2, 3}, 6: {2, 3}, 7: {3}}
CODE_NAME = {0: "N0PN", 1: "N1PN", 2: "N2PN", 3: "N3PN", 4: "N0CG", 5: "N1CG", 6: "N2CG", 7: "N3CG",
             0xc: "N0CE", 0xd: "N1CE", 0xe: "CPU", 0xf: "NA"}
# colours -> cell reads needed at 1x, 1/2, 1/4 (None: not allowed at that reduction)
COLOUR_COUNT = {16: (1, 2, 4), 256: (2, 4, None), 2048: (4, None, None), 32768: (4, None, None),
                16777216: (8, None, None)}
CYC_OFFSETS = (0x10, 0x12, 0x14, 0x16, 0x18, 0x1a, 0x1c, 0x1e)
TVMD, RAMCTL, BGON, CHCTLA, CHCTLB, PLSZ, ZMCTL = 0x00, 0x0e, 0x20, 0x28, 0x2a, 0x3a, 0x98
PNC = (0x30, 0x32, 0x34, 0x36)
MAPREGS = ((0x40, 0x42), (0x44, 0x46), (0x48, 0x4a), (0x4c, 0x4e))
TRACE_KEYS = CYC_OFFSETS + (TVMD, RAMCTL, BGON, CHCTLA, CHCTLB, PLSZ, ZMCTL) + PNC + tuple(r for p in MAPREGS for r in p)


class BadInput(Exception):
    pass


def num(x, what="value"):
    if isinstance(x, bool):
        raise BadInput(f"{what}: expected a number")
    if isinstance(x, int):
        return x
    try:
        return int(str(x), 0)
    except ValueError:
        raise BadInput(f"{what}: {x!r} is not a number")


def words_to_codes(words):
    """Eight words A0L,A0U,A1L,A1U,B0L,B0U,B1L,B1U -> {bank: 8 codes}. Low word is T0..T3, high is T4..T7, T0 in the top nibble."""
    if len(words) != 8:
        raise BadInput("need 8 cycle words")
    codes = {}
    for i, b in enumerate(BANKS):
        lo, hi = num(words[2 * i], "cycle word"), num(words[2 * i + 1], "cycle word")
        codes[b] = [(lo >> s) & 15 for s in (12, 8, 4, 0)] + [(hi >> s) & 15 for s in (12, 8, 4, 0)]
    return codes


def banks_of(lo, hi):
    return {b for b in BANKS if lo < BANK_BASE[b] + 0x20000 and hi > BANK_BASE[b]}


def make_layer(n, colours, red, bitmap=False, map_banks=None, cell_banks=None):
    if n >= 2 and (red != 1 or bitmap):
        raise BadInput(f"nbg{n}: only NBG0 and NBG1 have reduction or bitmaps")
    if red not in (1, 2, 4):
        raise BadInput(f"nbg{n}: reduction must be 1, 2 or 4")
    if colours not in COLOUR_COUNT:
        raise BadInput(f"nbg{n}: colours {colours} is not one of {sorted(COLOUR_COUNT)}")
    cnt = COLOUR_COUNT[colours]
    return dict(n=n, colours=colours, red=red, bitmap=bitmap, map_banks=map_banks, cell_banks=cell_banks,
                req_pn=0 if bitmap else red, req_cg=cnt[{1: 0, 2: 1, 4: 2}[red]])


def check(codes, layers, enabled, split_a, split_b, label="pattern", vcell_ok=False):
    """Judge decoded cycle codes. layers: list indexed by NBG number. Returns (errors, warnings, info)."""
    errs, warns, info = [], [], []
    for b, row in codes.items():
        for t, c in enumerate(row):
            if c in (0xc, 0xd):
                (info if vcell_ok else errs).append(
                    f"{label}: {b} T{t} vertical cell scroll read ({CODE_NAME[c]})" + (", not judged" if vcell_ok else " is not modelled"))
    bank_list = [b for b in BANKS if not ((b == "A1" and not split_a) or (b == "B1" and not split_b))]

    def fold(banks):
        banks = set(banks)
        if not split_a:
            banks = {"A0" if b == "A1" else b for b in banks}
        if not split_b:
            banks = {"B0" if b == "B1" else b for b in banks}
        return banks

    pn_banks = set()
    for n in sorted(enabled):
        if n >= len(layers) or layers[n] is None:
            raise BadInput(f"layer nbg{n} is enabled but not described")
        L = layers[n]
        pn_t = {b: [t for t, c in enumerate(codes[b]) if c == n] for b in bank_list}
        cg_t = {b: [t for t, c in enumerate(codes[b]) if c == n + 4] for b in bank_list}
        mbanks = fold(L["map_banks"]) if L["map_banks"] is not None else {b for b in bank_list if pn_t[b]}
        cbanks = fold(L["cell_banks"]) if L["cell_banks"] is not None else {b for b in bank_list if cg_t[b]}
        if L["bitmap"]:
            mbanks = set()
        if L["req_cg"] is None:
            errs.append(f"{label}: NBG{n} {L['colours']} colours at 1/{L['red']} reduction is not allowed (cell read table)")
            continue
        if not mbanks and not L["bitmap"]:
            errs.append(f"{label}: NBG{n} is enabled but has no pattern name reads")
        if not cbanks:
            errs.append(f"{label}: NBG{n} is enabled but has no cell reads")
        for b in sorted(mbanks):
            k = len(pn_t.get(b, []))
            if k < L["req_pn"]:
                errs.append(f"{label}: NBG{n} has {k} pattern name read(s) in {b} where its map lives, needs {L['req_pn']}")
            elif k > L["req_pn"]:
                warns.append(f"{label}: NBG{n} has {k} pattern name reads in {b}, {L['req_pn']} needed")
        for b in bank_list:
            if pn_t[b]:
                pn_banks.add(b)
                if b not in mbanks:
                    warns.append(f"{label}: NBG{n} has pattern name reads in {b} where it has no map")
        for b in sorted(cbanks):
            k = len(cg_t.get(b, []))
            if k < L["req_cg"]:
                errs.append(f"{label}: NBG{n} has {k} cell read(s) in {b} where its cells live, needs {L['req_cg']}")
            elif k > L["req_cg"]:
                warns.append(f"{label}: NBG{n} has {k} cell reads in {b}, {L['req_cg']} needed")
        for b in bank_list:
            if cg_t[b] and b not in cbanks:
                warns.append(f"{label}: NBG{n} has cell reads in {b} where it has no cells")
        all_pn = sorted({t for b in bank_list for t in pn_t[b]})
        all_cg = sorted({t for b in bank_list for t in cg_t[b]})
        if not (n < 2 and 0 in all_pn):   # NBG0/NBG1 names at T0 put no limit on cell timings
            for p in all_pn:
                for c in all_cg:
                    if c not in LEGAL[p]:
                        errs.append(f"{label}: NBG{n} cell read at T{c} is not allowed with a name read at T{p}")
    for (b0, b1), split in ((("A0", "A1"), split_a), (("B0", "B1"), split_b)):
        if split:
            for t in range(8):
                if (codes[b0][t] == 0xe) != (codes[b1][t] == 0xe):
                    errs.append(f"{label}: CPU access at T{t} in only one of {b0}/{b1}; split banks need it in both")
            cpu = [t for t in range(8) if codes[b0][t] == 0xe and codes[b1][t] == 0xe]
            for t in cpu:
                pt = (t - 1) % 8
                if pt in cpu:
                    continue   # inside a run: only the first slot needs the no-access slot in front
                if not (codes[b0][pt] == 0xf and codes[b1][pt] == 0xf):
                    errs.append(f"{label}: CPU run at T{t} of {b0}/{b1} is not preceded by no access in both banks "
                                f"(T{pt} is {CODE_NAME.get(codes[b0][pt])}/{CODE_NAME.get(codes[b1][pt])})")
        else:
            cpu = [t for t in range(8) if codes[b0][t] == 0xe]
            for t in cpu:
                if (t - 1) % 8 not in cpu and codes[b0][(t - 1) % 8] != 0xf:
                    errs.append(f"{label}: CPU run at T{t} of {b0} is not preceded by no access")
        if not cpu:
            warns.append(f"{label}: no CPU slot in {b0}/{b1}: SH-2 writes to that VRAM can only finish in the blanking periods")
        else:
            info.append(f"{label}: CPU slots {b0}/{b1}: T{','.join(map(str, cpu))}")
    if ("A0" in pn_banks and "B0" in pn_banks) or ("A1" in pn_banks and "B1" in pn_banks):
        errs.append(f"{label}: pattern name reads in both {sorted(pn_banks)}: only one of A0/B0 and one of A1/B1 allowed")
    return errs, warns, info


# ---- writer scan ----

# Registers whose values the rules above read: RAMCTL, the cycle words, character/colour control, plane size, pattern names, maps, zoom/reduction.
WATCH = {0x0e, *CYC_OFFSETS, 0x28, 0x2a, 0x30, 0x32, 0x34, 0x36, 0x3a, 0x40, 0x42, 0x44, 0x46, 0x48, 0x4a, 0x4c, 0x4e, 0x98}
DEFAULT_WRITERS = ("SAT_VDP2_REG", "sat_v2l_write")
DEFAULT_OK = r"\bSAT_(?:V2|CYC)_\w+"
SCAN_SUFFIXES = {".c", ".h", ".inc"}


def load_writer_allow(path):
    """`file | substring | reason` lines -> [(file, substring, reason)]."""
    allow = []
    if not path:
        return allow
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise BadInput(f"cannot read allowlist {path}: {e}")
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        f = [x.strip() for x in line.split("|")]
        if len(f) < 3 or not f[0] or not f[1] or not "|".join(f[2:]).strip():
            raise BadInput(f"{path}:{n}: need `file | substring | reason`")
        allow.append((f[0], f[1], "|".join(f[2:]).strip()))
    return allow


def scan_writers(root, allow, writers=DEFAULT_WRITERS, skip_ifdefs=(), ok_pattern=DEFAULT_OK):
    """-> (problems, covered writes seen, stale allowlist entries). Paths in messages and in the allowlist are relative to root."""
    root = pathlib.Path(root)
    if not root.is_dir():
        raise BadInput(f"not a folder: {root}")
    names = "|".join(re.escape(w) for w in writers)
    rx = re.compile(r"\b(?:" + names + r")\(\s*(?:[^,()]+,\s*)?(0x[0-9a-fA-F]+)\s*(?:\)\s*=\s*([^;]+);|,\s*([^;]+)\);)")
    ok = re.compile(ok_pattern)
    problems, seen, used = [], 0, set()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        depth, skip_depth, skipping = 0, 0, False
        for no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            st = line.strip()
            if st.startswith("#if"):
                depth += 1
                if not skipping and any(re.match(r"#ifdef\s+" + re.escape(n) + r"\b", st) for n in skip_ifdefs):
                    skipping, skip_depth = True, depth
            elif st.startswith("#endif"):
                if skipping and depth == skip_depth:
                    skipping = False
                depth -= 1
            if skipping:
                continue
            code = re.sub(r"/\*.*?\*/", "", line).split("//", 1)[0]
            for m in rx.finditer(code):
                off = int(m.group(1), 16)
                if off not in WATCH:
                    continue
                rhs = (m.group(2) or m.group(3) or "").strip()
                seen += 1
                if ok.search(rhs):
                    continue
                hit = next((i for i, (f, sub, _) in enumerate(allow) if f == rel and sub in line), None)
                if hit is not None:
                    used.add(hit)
                    continue
                problems.append(f"{rel}:{no}: write of VDP2 {off:#05x} = {rhs} is not from a layout macro and not on the writers allowlist")
    stale = [f"{f} | {sub} | {why}" for i, (f, sub, why) in enumerate(allow) if i not in used]
    return problems, seen, stale


# ---- spec files ----

def load_spec(path):
    p = pathlib.Path(path)
    try:
        spec = json.loads(p.read_text(encoding="utf-8")) if p.suffix.lower() == ".json" else cfg.load(p)
    except (OSError, ValueError) as e:
        raise BadInput(f"cannot read spec {path}: {e}")
    if not isinstance(spec, dict):
        raise BadInput("spec must be a map")
    return spec


def split_flags(spec, ramctl=None):
    if "ramctl" in spec or ramctl is not None:
        r = ramctl if ramctl is not None else num(spec["ramctl"], "ramctl")
        return bool(r & 0x100), bool(r & 0x200)
    return bool(spec.get("split_a", True)), bool(spec.get("split_b", True))


def banks_list(v, what):
    if v is None:
        return None
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",") if x.strip()]
    bad = [b for b in v if b not in BANKS]
    if bad:
        raise BadInput(f"{what}: unknown bank {bad[0]!r}")
    return set(v)


def layers_from_spec(spec):
    out = [None] * 4
    for n in range(4):
        d = (spec.get("layers") or {}).get(f"nbg{n}")
        if d:
            out[n] = make_layer(n, num(d.get("colours", 16), "colours"), num(d.get("reduction", 1), "reduction"),
                                bool(d.get("bitmap", False)), banks_list(d.get("map_banks"), f"nbg{n}.map_banks"),
                                banks_list(d.get("cell_banks"), f"nbg{n}.cell_banks"))
    return out


def check_spec(spec, words=None):
    words = words if words is not None else spec.get("cycles")
    if not words:
        raise BadInput("spec has no cycles (8 words)")
    codes = words_to_codes(list(words))
    layers = layers_from_spec(spec)
    if not any(layers):
        raise BadInput("spec describes no layers")
    split_a, split_b = split_flags(spec)
    profiles = spec.get("profiles") or {"all": [n for n in range(4) if layers[n]]}
    errs, warns, info = [], [], []
    for name, enabled in profiles.items():
        e, w, i = check(codes, layers, {num(x, "layer") for x in enabled}, split_a, split_b, str(name),
                        bool(spec.get("vertical_cell_scroll_ok", False)))
        errs += e; warns += w; info += i
    return errs, warns, info


# ---- register-write traces ----

def layers_from_regs(regs, overrides=None):
    """Decode layer set-up from register values. Map banks come from the map registers (map offset registers assumed 0)."""
    g = lambda o: regs.get(o, 0)
    overrides = overrides or {}
    layers = []
    for n in range(4):
        if n < 2:
            sh = 8 * n
            big, bitmap = (g(CHCTLA) >> sh) & 1, (g(CHCTLA) >> (sh + 1)) & 1
            cc = (g(CHCTLA) >> (sh + 4)) & (7 if n == 0 else 3)
            colours = {0: 16, 1: 256, 2: 2048, 3: 32768, 4: 16777216}.get(cc)
            zm = (g(ZMCTL) >> (8 * n)) & 3
            red = 4 if zm & 2 else 2 if zm & 1 else 1
        else:
            big = (g(CHCTLB) >> (0 if n == 2 else 4)) & 1
            bitmap, red = 0, 1
            colours = {0: 16, 1: 256}[(g(CHCTLB) >> (1 if n == 2 else 5)) & 1]
        if colours is None:
            raise BadInput(f"nbg{n}: reserved colour code in the character control register")
        word2 = ((g(PNC[n]) >> 15) & 1) == 0
        page_bytes = (32 * 32 if big else 64 * 64) * (4 if word2 else 2)
        pages = {0: 1, 1: 2, 2: 2, 3: 4}[(g(PLSZ) >> (2 * n)) & 3]
        starts = set()
        for w in (g(MAPREGS[n][0]), g(MAPREGS[n][1])):
            for v in (w & 0x3f, (w >> 8) & 0x3f):
                starts.add((v & ~(pages - 1)) * page_bytes)
        mb = set()
        for s in starts:
            mb |= banks_of(s, s + pages * page_bytes)
        ov = overrides.get(f"nbg{n}") or {}
        layers.append(make_layer(n, colours, red, bool(bitmap),
                                 banks_list(ov["map_banks"], "map_banks") if "map_banks" in ov else mb,
                                 banks_list(ov.get("cell_banks"), "cell_banks")))
    return layers


def judge_regs(regs, spec):
    layers = layers_from_regs(regs, spec.get("layers"))
    enabled = {n for n in range(4) if regs.get(BGON, 0) >> n & 1}
    split_a, split_b = split_flags(spec, regs.get(RAMCTL, 0))
    return check(words_to_codes([regs.get(o, 0) for o in CYC_OFFSETS]), layers, enabled, split_a, split_b, "state",
                 bool(spec.get("vertical_cell_scroll_ok", False)))


REG_LINE = re.compile(r"(?:^|\s)((?:0[xX])?[0-9A-Fa-f]+)\s+((?:0[xX])?[0-9A-Fa-f]+)\s*$")


def parse_write(line):
    m = REG_LINE.search(line)
    if not m:
        return None
    addr, val = int(m.group(1), 16), int(m.group(2), 16)
    off = addr - 0x25F80000 if addr >= 0x25F80000 else addr
    if off < 0 or off >= 0x200 or off % 2 or val > 0xffff:
        return None
    return off, val


def check_trace(lines, spec):
    """Replay register writes; judge the state at the end of every burst. Returns (bursts, {state key: [errs, count, regs]})."""
    regs, in_burst, bursts, states = {}, False, 0, {}
    req = spec.get("require_ramctl")
    req = num(req, "require_ramctl") if req is not None else None

    def judge_now():
        nonlocal bursts
        if not (regs.get(TVMD, 0) & 0x8000) or not (regs.get(BGON, 0) & 0xf):
            return
        if req is not None and regs.get(RAMCTL, 0) != req:
            return   # another program's screen (boot menu, logo): not ours to judge
        bursts += 1
        key = tuple(regs.get(o, 0) for o in TRACE_KEYS)
        if key in states:
            states[key][1] += 1
            return
        errs, _, _ = judge_regs(regs, spec)
        states[key] = [errs, 1, dict(regs)]

    for raw in list(lines) + [""]:
        s = raw.strip()
        if s.startswith("#"):
            continue
        w = parse_write(s) if s else None
        if w:
            regs[w[0]] = w[1]
            in_burst = True
        else:
            if in_burst:
                judge_now()
            in_burst = False
    return bursts, states


def fmt(msgs, tag, quiet=False):
    for m in msgs:
        if not quiet or tag == "ERROR":
            print(tag, m)


def main(argv=None):
    ap = argparse.ArgumentParser(description="VDP2 VRAM access-cycle rule checker")
    ap.add_argument("spec", nargs="?")
    ap.add_argument("--scan-writers", metavar="SRCDIR", help="scan C sources for writes of the covered registers that bypass the layout macros (see the header)")
    ap.add_argument("--allow", help="writer scan: allowlist file, lines `file | substring | reason`")
    ap.add_argument("--writer", action="append", help="writer scan: a register write macro or function name (default SAT_VDP2_REG, sat_v2l_write); repeatable")
    ap.add_argument("--skip-ifdef", action="append", default=[], help="writer scan: skip the #ifdef NAME blocks of a build that never ships; repeatable")
    ap.add_argument("--ok-pattern", default=DEFAULT_OK, help="writer scan: a value matching this regex counts as coming from the layout macros")
    ap.add_argument("--trace", help="register-write trace to replay instead of the spec's cycle words")
    ap.add_argument("--cyc", help="eight hex cycle words A0L,A0U,A1L,A1U,B0L,B0U,B1L,B1U overriding the spec")
    ap.add_argument("--quiet", action="store_true", help="errors only")
    ap.add_argument("--limit", type=int, default=8, help="trace: distinct states to list")
    a = ap.parse_args(argv)
    try:
        scan_fail = 0
        if a.scan_writers:
            problems, seen, stale = scan_writers(a.scan_writers, load_writer_allow(a.allow), tuple(a.writer or DEFAULT_WRITERS), a.skip_ifdef, a.ok_pattern)
            print(f"writer scan: {seen} covered register writes in {a.scan_writers}, {len(problems)} not from a layout macro or the allowlist")
            fmt(problems, "ERROR")
            fmt([f"stale allowlist entry (matches no write): {x}" for x in stale], "warning", a.quiet)
            scan_fail = 1 if problems else 0
            if not a.spec:
                print("vdp2_cycle_check:", f"FAIL ({len(problems)} writers)" if problems else "PASS")
                return scan_fail
        if not a.spec:
            raise BadInput("a spec file is needed (or --scan-writers SRCDIR)")
        spec = load_spec(a.spec)
        if a.trace:
            try:
                lines = pathlib.Path(a.trace).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError as e:
                raise BadInput(f"cannot read trace: {e}")
            bursts, states = check_trace(lines, spec)
            bad = [v for v in states.values() if v[0]]
            print(f"{bursts} bursts judged with the display on, {len(states)} distinct states, {len(bad)} break a rule")
            for v in sorted(states.values(), key=lambda v: -v[1])[:a.limit]:
                r = v[2]
                print(f"  x{v[1]:<5} cycles {' '.join('%04x' % r.get(o, 0) for o in CYC_OFFSETS)} BGON {r.get(BGON, 0):02x} -> "
                      + ("FAIL: " + v[0][0] if v[0] else "ok"))
            print("vdp2_cycle_check:", f"FAIL ({len(bad)} states)" if bad else "PASS")
            return 1 if bad or scan_fail else 0
        words = [int(x, 16) for x in a.cyc.split(",")] if a.cyc else None
        errs, warns, info = check_spec(spec, words)
    except BadInput as e:
        print("bad input:", e, file=sys.stderr)
        return 2
    fmt(errs, "ERROR")
    fmt(warns, "warning", a.quiet)
    fmt(info, "info", a.quiet)
    print("vdp2_cycle_check:", f"FAIL ({len(errs)} errors)" if errs else "PASS")
    return 1 if errs or scan_fail else 0


if __name__ == "__main__":
    sys.exit(main())
