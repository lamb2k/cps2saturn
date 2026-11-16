#!/usr/bin/env python3
"""Hot code placement plan: which functions go in the fast RAM, and where the others go. Writes linker include lists.

Moved from avpsaturn v0.1.0-beta, saturn/rt/build.py plan_functions (lane perf-hw, 2026-11-12; MIT, owner's own code), with the AvP regions and files
removed: regions, budgets and the heat file are inputs.

Why: the Saturn's high work RAM runs the SH-2 without wait states and low work RAM and the cart are slow (AvP measured about 14 clocks a long write in low RAM).
Code that does not fit high RAM should be the code that runs least. Measure which functions run (tools/fn_heat.py), rank them by cost per byte, and place
the hottest in the fast region up to its capacity. Everything else leaves the fast region into the regions the promoted functions came from, so every
region keeps its size and nothing else moves. Behaviour is untouched: only addresses move.

usage: place_plan.py --heat heat.json --functions funcs.json --fast hw --capacity BYTES [--slack BYTES] [--spare REGION=BYTES ...] [--out plan.json] [--ld-dir DIR]
  heat.json       {"obj:sym": {"exec": n, "ifill": n}}      (fn_heat.py)
  funcs.json      [{"key": "obj:sym", "size": bytes, "region": "hw"}]   every function of a -ffunction-sections build and the region it sits in now
  --capacity      code bytes the fast region can hold after its data (the rest of the region is not this tool's)
  --spare         bytes a region can take beyond what the promoted functions freed (low work RAM, when data moved out of the fast region)
  --ld-dir        writes REGION.ld.inc with one `*obj.o(.text.sym)` line per function, for a link script's section list
Score = (exec + 16 * ifill) / size. A function with no heat is never promoted. Exit 0, 2 bad input.
"""
import argparse
import json
import sys

IFILL_WEIGHT = 16


def plan(heat, funcs, fast, capacity, slack=0, pad=1, spare=None):
    """Returns (promote, demote, report). promote: {region: [func]}, demote: {region: [func]}, each func (key, size).
    spare: {region: bytes} a region can take on top of what its promoted functions freed (low work RAM has room that the cart tail does not)."""
    scored = []
    for f in funcs:
        h = heat.get(f["key"]) or {"exec": 0, "ifill": 0}
        scored.append(((h["exec"] + IFILL_WEIGHT * h["ifill"]) / max(f["size"], 1), f))
    scored.sort(key=lambda t: -t[0])
    cap = capacity + slack
    keep, used = set(), 0
    # first: every function that ran and already sits in the fast region stays; then the rest by cost per byte
    for sc, f in scored:
        if f["region"] == fast and sc > 0 and used + f["size"] <= cap:
            keep.add(f["key"]); used += f["size"]
    for sc, f in scored:
        if sc > 0 and f["key"] not in keep and used + f["size"] <= cap:
            keep.add(f["key"]); used += f["size"]
    promote, demote_c = {}, []
    for sc, f in scored:
        if f["region"] != fast and f["key"] in keep:
            promote.setdefault(f["region"], []).append(f)
        elif f["region"] == fast and f["key"] not in keep:
            demote_c.append(f)
    # each region takes back what its promoted functions freed, less one byte of alignment per function
    budget = {r: sum(x["size"] for x in l) for r, l in promote.items()}
    for r, extra in (spare or {}).items():
        budget[r] = budget.get(r, 0) + extra
    demote, left = {}, 0
    for f in sorted(demote_c, key=lambda x: -x["size"]):   # largest first: the regions fill exactly
        for r in sorted(budget, key=lambda r: -budget[r]):
            if budget[r] >= f["size"] + pad:
                budget[r] -= f["size"] + pad
                demote.setdefault(r, []).append(f)
                break
        else:
            left += f["size"]
    rep = {
        "fast_code_before": sum(f["size"] for f in funcs if f["region"] == fast),
        "fast_code_kept": used,
        "functions_with_heat": sum(1 for sc, _ in scored if sc > 0),
        "functions_promoted": sum(len(v) for v in promote.values()),
        "promoted_bytes": {r: sum(x["size"] for x in l) for r, l in promote.items()},
        "demoted_bytes": {r: sum(x["size"] for x in l) for r, l in demote.items()},
        "bytes_without_room": left,
    }
    return promote, demote, rep


def ld_lines(items):
    """Linker section patterns for (key, size) functions: obj:sym -> *obj.o(.text.sym)."""
    out = []
    for f in items:
        obj, _, sym = f["key"].partition(":")
        out.append(f"    *{obj}.o(.text.{sym})")
    return "\n".join(out) + ("\n" if out else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--heat", required=True)
    ap.add_argument("--functions", required=True)
    ap.add_argument("--fast", required=True)
    ap.add_argument("--capacity", type=int, required=True)
    ap.add_argument("--slack", type=int, default=0)
    ap.add_argument("--spare", action="append", default=[], metavar="REGION=BYTES")
    ap.add_argument("--out")
    ap.add_argument("--ld-dir")
    a = ap.parse_args(argv)
    try:
        heat = json.load(open(a.heat))
        funcs = json.load(open(a.functions))
    except (OSError, ValueError) as e:
        print(f"place_plan: {e}", file=sys.stderr)
        return 2
    try:
        spare = {k: int(v) for k, _, v in (x.partition("=") for x in a.spare)}
    except ValueError:
        print("place_plan: --spare wants REGION=BYTES", file=sys.stderr)
        return 2
    promote, demote, rep = plan(heat, funcs, a.fast, a.capacity, a.slack, spare=spare)
    print(json.dumps(rep, indent=1))
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"promote": promote, "demote": demote, "report": rep}, f, indent=1)
    if a.ld_dir:
        import pathlib
        d = pathlib.Path(a.ld_dir)
        d.mkdir(parents=True, exist_ok=True)
        fast_keep = sorted({f["key"] for f in funcs if f["region"] == a.fast} - {x["key"] for l in demote.values() for x in l}
                           | {x["key"] for l in promote.values() for x in l})
        sizes = {f["key"]: f for f in funcs}
        (d / f"{a.fast}.ld.inc").write_text(ld_lines([sizes[k] for k in fast_keep]))
        for r, l in demote.items():
            (d / f"{r}.ld.inc").write_text(ld_lines(l))
    return 0


if __name__ == "__main__":
    sys.exit(main())
