#!/usr/bin/env python3
"""Per-stage round file planning: shared pages, keep sets, restore lists and ranked tile drops.

Input census JSON (counts and addresses only, from your MAME routes):
{
  "page_size": 1024,                                     optional; else rounds.page_size from --config
  "stages": {
    "02": {"pages": [page numbers read], "keys": {"<tile key>": score, ...}, "room": tiles that fit},
    ...
  },
  "spill": {"02": [page numbers this stage's file overwrites with tiles], ...}       optional
}
Scores: higher means more needed. A rule that worked: 1000 per real full-route section that drew the key,
500 if a KO or continue drew it, 1 per walk that drew it.

Rules:
- A page read by at least shared_min stages is kept in every stage (a mode or setting can read common tables the
  stage's own walk never touched).
- Every page any file overwrites is restored by each stage that reads it.
- When keys exceed room, the lowest scores drop first; ties drop the highest key first.

usage: page_plan.py CENSUS.json [--config C] [--shared-min N] [--out PLAN.json]
Prints a per-stage summary. PLAN.json holds keep sets, restore lists and dropped keys.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys


def plan(census: dict, shared_min: int) -> dict:
    stages = census["stages"]
    seen = collections.Counter()
    for s in stages.values():
        seen.update(set(s.get("pages", [])))
    shared = sorted(p for p, n in seen.items() if n >= shared_min)
    spill = {k: set(v) for k, v in census.get("spill", {}).items()}
    written = set().union(*spill.values()) if spill else set()
    out = {"shared_pages": shared, "stages": {}}
    for name, s in stages.items():
        keep = set(s.get("pages", [])) | set(shared)
        restore = sorted(keep & (written - spill.get(name, set())))
        clash = sorted(keep & spill.get(name, set()))
        keys = {int(k, 0) if isinstance(k, str) else int(k): v for k, v in s.get("keys", {}).items()}
        room = s.get("room", len(keys))
        order = sorted(keys, key=lambda k: (-keys[k], k))
        kept, dropped = order[:room], order[room:]
        out["stages"][name] = {
            "keep_pages": sorted(keep), "restore_pages": restore, "own_spill_on_kept_page": clash,
            "kept_keys": len(kept), "dropped_keys": sorted(dropped),
            "dropped_score": sum(keys[k] for k in dropped),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("census", type=pathlib.Path)
    ap.add_argument("--config")
    ap.add_argument("--shared-min", type=int)
    ap.add_argument("--out", type=pathlib.Path)
    a = ap.parse_args(argv)
    census = json.loads(a.census.read_text())
    smin = a.shared_min
    if smin is None and a.config:
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        import cfg
        smin = cfg.get(cfg.load(a.config), "rounds.shared_min")
    p = plan(census, smin or 10)
    print("shared pages", len(p["shared_pages"]))
    for name, s in sorted(p["stages"].items()):
        warn = f" WARNING own spill on {len(s['own_spill_on_kept_page'])} kept pages" if s["own_spill_on_kept_page"] else ""
        print(f"{name}: keep {len(s['keep_pages'])} pages, restore {len(s['restore_pages'])}, "
              f"keys kept {s['kept_keys']} dropped {len(s['dropped_keys'])} (score {s['dropped_score']}){warn}")
    if a.out:
        a.out.write_text(json.dumps(p, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
