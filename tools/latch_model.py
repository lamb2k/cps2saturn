#!/usr/bin/env python3
"""Exhaustive interleaving model of a publish/apply protocol for display registers (Saturn, two SH-2s).

The lesson: one CPU (the writer) prepares the next picture's register values while the other (the vblank handler)
copies them to the video chip. If the handler latches each register as it goes, a vblank that lands in the middle of
the writer's update copies some new and some old registers: a picture that mixes two frames, rarely, only on real
timing, and never in a single-stepped test. Checking afterwards and retrying does not help, because the chip already
took the mixed values. The fix is a sequence word: the writer makes it odd, stores the record, makes it even; the
handler reads the sequence, copies the whole record to a private snapshot, reads the sequence again, and only writes
the chip from the snapshot if the sequence was even and unchanged. This model walks every interleaving of the writer
(publishing up to K records) and one handler run, one memory access per step, and reports how many end states leave
the chip with a mixed record. It models the protocol, not any C code; transcribe your own steps if yours differ.

Variants:
  naive     copy each register straight to the chip as it is read, no sequence word
  retry     copy straight to the chip, then verify the sequence and try again (bounded): still writes mixed values
  sequence  snapshot, verify, then write the chip from the snapshot (never mixed)
usage: latch_model.py [--regs N] [--records K] [--tries T] [--variant naive|retry|sequence ...]
Exit 0 when the sequence variant never mixes and every other variant asked for does, 1 otherwise, 2 bad input.
"""
from __future__ import annotations

import argparse
import sys

VARIANTS = ("naive", "retry", "sequence")


def records_for(n_regs: int, n_records: int):
    return [tuple(10 * (r + 1) + i for i in range(n_regs)) for r in range(n_records)]


def writer_program(n_regs: int, n_records: int):
    prog = []
    for r in range(n_records):
        prog += [("q", r), ("odd", r)]
        for i in range(n_regs):
            prog += [("pub", r, i), ("pv", r, i)]
        prog.append(("even", r))
    return prog


def writer_step(op, st, records):
    """st = (index, seq_seen, seq, pub, valid)."""
    si, sq, seq, pub, pv = st
    if op[0] == "q":
        sq = seq
    elif op[0] == "odd":
        seq = sq + 1
    elif op[0] == "pub":
        pub = pub[:op[2]] + (records[op[1]][op[2]],) + pub[op[2] + 1:]
    elif op[0] == "pv":
        pv = pv[:op[2]] + (1,) + pv[op[2] + 1:]
    elif op[0] == "even":
        seq = sq + 2
    return (si + 1, sq, seq, pub, pv)


def put(tup, i, v):
    return tup[:i] + (v,) + tup[i + 1:]


def handler_step(m, mem, variant, n, tries):
    """m = (stage, try, i, seq_read, snapshot, snapshot_valid, chip); mem = (seq, pub, valid)."""
    stage, t, i, q, snap, sv, chip = m
    seq, pub, pv = mem
    if stage == "start":
        return ("done", t, i, q, snap, sv, chip) if t >= tries else ("chk", t, i, seq, snap, sv, chip)
    if variant == "naive":
        if stage == "chk":
            return ("loop", t, 0, q, snap, sv, chip)
        if stage == "loop":
            if pv[i]:
                chip = put(chip, i, pub[i])
            return ("done" if i + 1 == n else "loop", t, i + 1, q, snap, sv, chip)
    elif variant == "retry":
        if stage == "chk":
            return ("start", t + 1, 0, q, snap, sv, chip) if q & 1 else ("loop", t, 0, q, snap, sv, chip)
        if stage == "loop":
            if pv[i]:
                chip = put(chip, i, pub[i])
            return ("verify" if i + 1 == n else "loop", t, i + 1, q, snap, sv, chip)
        if stage == "verify":
            return ("done" if seq == q else "start", t + (seq != q), i, q, snap, sv, chip)
    else:
        if stage == "chk":
            return ("start", t + 1, 0, q, snap, sv, chip) if q & 1 else ("copy", t, 0, q, snap, sv, chip)
        if stage == "copy":
            snap, sv = put(snap, i, pub[i]), put(sv, i, pv[i])
            return ("verify" if i + 1 == n else "copy", t, i + 1, q, snap, sv, chip)
        if stage == "verify":
            return ("write", t, 0, q, snap, sv, chip) if seq == q else ("start", t + 1, 0, q, snap, sv, chip)
        if stage == "write":
            if sv[i]:
                chip = put(chip, i, snap[i])
            return ("done" if i + 1 == n else "write", t, i + 1, q, snap, sv, chip)
    raise AssertionError(stage)


def explore(variant: str, n_regs: int = 3, n_records: int = 3, tries: int = 4):
    """Returns (states, terminal states, terminal states with a mixed chip, one example chip or None)."""
    records = records_for(n_regs, n_records)
    prog = writer_program(n_regs, n_records)
    untouched = (None,) * n_regs
    complete = lambda chip: chip == untouched or chip in records
    s0 = (0, 0, 0, (0,) * n_regs, (0,) * n_regs)
    m0 = ("start", 0, 0, 0, (0,) * n_regs, (0,) * n_regs, untouched)
    seen, todo = {(s0, m0)}, [(s0, m0)]
    terminals = bad = 0
    example = None
    while todo:
        s, m = todo.pop()
        if m[0] == "done":
            terminals += 1
            if not complete(m[6]):
                bad += 1
                example = example or m[6]
            continue
        nxt = [(s, handler_step(m, (s[2], s[3], s[4]), variant, n_regs, tries))]
        if s[0] < len(prog):
            nxt.append((writer_step(prog[s[0]], s, records), m))
        for x in nxt:
            if x not in seen:
                seen.add(x)
                todo.append(x)
    return len(seen), terminals, bad, example


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="publish/apply protocol model")
    ap.add_argument("--regs", type=int, default=3)
    ap.add_argument("--records", type=int, default=3)
    ap.add_argument("--tries", type=int, default=4)
    ap.add_argument("--variant", action="append", choices=VARIANTS)
    a = ap.parse_args(argv)
    if a.regs < 2 or a.records < 1 or a.tries < 1:
        print("bad input: need --regs >= 2, --records >= 1, --tries >= 1", file=sys.stderr)
        return 2
    ok = True
    for v in a.variant or VARIANTS:
        states, term, bad, ex = explore(v, a.regs, a.records, a.tries)
        print(f"{v:9s} {states} states, {term} end states, {bad} leave a mixed record on the chip"
              + (f", e.g. {ex}" if ex else ""))
        ok &= (bad == 0) if v == "sequence" else (bad > 0)
    print("latch_model:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
