#!/usr/bin/env python3
"""CD-R sector budget for a Saturn disc: data track plus CDDA tracks plus pregaps.

usage: disc_budget.py CUE [--cdr-sectors 360000] [--pregap 150]
       disc_budget.py --data DATA.iso --tracks DIR [--glob 't*.raw'] [...]
Data sectors = bytes / 2048 (MODE1/2048) or / 2352 (raw MODE1/2352); audio sectors = bytes / 2352.
Each audio track counts one pregap (default 150 sectors, 2 s) unless the cue names its own.
80-minute CD-R: 360,000 sectors. 74-minute: 333,000. Exit 1 when over.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys


def sectors(size: int, mode: str) -> int:
    per = 2048 if mode.endswith("2048") else 2352
    return -(-size // per)


def from_cue(cue: pathlib.Path, pregap_default: int) -> tuple[int, int, int, int]:
    data = audio = gaps = tracks = 0
    cur_file = None
    for line in cue.read_text().splitlines():
        s = line.strip()
        m = re.match(r'FILE\s+"([^"]+)"', s)
        if m:
            cur_file = cue.parent / m[1]
            continue
        m = re.match(r"TRACK\s+\d+\s+(\S+)", s)
        if m and cur_file is not None:
            mode = m[1]
            n = sectors(cur_file.stat().st_size, mode)
            if mode == "AUDIO":
                audio += n
                tracks += 1
            else:
                data += n
            continue
        m = re.match(r"PREGAP\s+(\d+):(\d+):(\d+)", s)
        if m:
            gaps += (int(m[1]) * 60 + int(m[2])) * 75 + int(m[3])
    return data, audio, gaps, tracks


def report(data: int, audio: int, gaps: int, tracks: int, limit: int) -> int:
    total = data + audio + gaps
    print(f"data {data}, audio {audio} in {tracks} tracks, pregaps {gaps}, total {total} of {limit}")
    if total > limit:
        print(f"OVER by {total - limit} sectors ({(total - limit) / 75 / 60:.1f} min)")
        return 1
    print(f"fits, {limit - total} sectors spare ({(limit - total) / 75 / 60:.1f} min)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cue", nargs="?", type=pathlib.Path)
    ap.add_argument("--data", type=pathlib.Path)
    ap.add_argument("--tracks", type=pathlib.Path)
    ap.add_argument("--glob", default="t*.raw")
    ap.add_argument("--cdr-sectors", type=int, default=360000)
    ap.add_argument("--pregap", type=int, default=150)
    a = ap.parse_args(argv)
    if a.cue:
        d, au, g, t = from_cue(a.cue, a.pregap)
    elif a.data:
        d = sectors(a.data.stat().st_size, "MODE1/2048")
        files = sorted(a.tracks.glob(a.glob)) if a.tracks else []
        au = sum(sectors(f.stat().st_size, "AUDIO") for f in files)
        t, g = len(files), len(files) * a.pregap
    else:
        ap.error("give a cue, or --data")
    return report(d, au, g, t, a.cdr_sectors)


if __name__ == "__main__":
    sys.exit(main())
