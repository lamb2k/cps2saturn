#!/usr/bin/env python3
"""Write a Saturn cue (data track + CDDA tracks) and SHA256SUMS.txt for a package folder.

usage: make_cue.py OUT_DIR DATA.iso [--tracks DIR] [--glob 't*.raw'] [--name NAME] [--commit HASH] [--copy]
  Tracks are raw 44.1 kHz stereo 16-bit little-endian, one file per track, numbered from 02 in name order.
  The cue names them BINARY, which burn tools and optical drive emulators read as CD audio in this byte order.
  --copy copies the image and tracks into OUT_DIR; without it they must already be there.
  SHA256SUMS.txt starts with a '# commit' line (sha256sum -c skips it).
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys


def cue_text(data_name: str, tracks: list[str]) -> str:
    cue = f'FILE "{data_name}" BINARY\n  TRACK 01 MODE1/2048\n    INDEX 01 00:00:00\n'
    for n, t in enumerate(tracks, 2):
        cue += f'FILE "{t}" BINARY\n  TRACK {n:02d} AUDIO\n    PREGAP 00:02:00\n    INDEX 01 00:00:00\n'
    return cue


def sha_file(out: pathlib.Path, commit: str | None) -> str:
    lines = [f"# commit {commit}"] if commit else []
    for f in sorted(out.iterdir()):
        if f.is_file() and f.name != "SHA256SUMS.txt":
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            lines.append(f"{h.hexdigest()}  {f.name}")
    text = "\n".join(lines) + "\n"
    (out / "SHA256SUMS.txt").write_text(text, newline="\n")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=pathlib.Path)
    ap.add_argument("data", type=pathlib.Path)
    ap.add_argument("--tracks", type=pathlib.Path)
    ap.add_argument("--glob", default="t*.raw")
    ap.add_argument("--name")
    ap.add_argument("--commit")
    ap.add_argument("--copy", action="store_true")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    tracks = sorted(a.tracks.glob(a.glob)) if a.tracks else []
    for t in tracks:
        if t.stat().st_size % 2352:
            print(f"warning: {t.name} is not a whole number of 2352-byte sectors")
    if a.copy:
        shutil.copy(a.data, a.out / a.data.name)
        for t in tracks:
            shutil.copy(t, a.out / t.name)
    name = a.name or a.data.stem
    (a.out / f"{name}.cue").write_text(cue_text(a.data.name, [t.name for t in tracks]), newline="\n")
    print(sha_file(a.out, a.commit), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
