#!/usr/bin/env python3
"""Pre-push hygiene scan: no game material, no private paths, no secrets.

usage: hygiene_scan.py [ROOT] [--all]
  ROOT   repository to scan (default: this repo)
  --all  scan every file under ROOT, not only the ones git tracks or would add

Checks, per file:
  - blocked types: ROMs, disc images, audio, images, save states, archives;
  - size over 512 KB;
  - binary content (NUL bytes) in any file;
  - private paths (drive-letter paths, home folders), private IPs, tokens and keys.
Exit 0 when clean, 1 with a list of findings otherwise.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

BLOCKED = {
    ".zip", ".7z", ".rar", ".rom", ".bin", ".iso", ".cue", ".chd", ".gdi", ".cdi", ".mds", ".mdf", ".img",
    ".raw", ".wav", ".pcm", ".mp3", ".ogg", ".flac", ".sta", ".state", ".nv", ".nvram",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".mp4", ".avi", ".mkv", ".elf", ".o", ".a",
}
MAX_BYTES = 512 * 1024

# Built from parts so this file does not flag itself.
_D = "[A-Za-z]" + ":" + r"[\\/]"
PATTERNS = {
    "drive-letter path": re.compile(r"(?<![A-Za-z0-9])" + _D + r"[A-Za-z0-9_.]"),
    "home folder": re.compile("/" + "home/" + r"[a-z]|/" + "Users/" + r"[A-Za-z]|\\" + "Users" + r"\\|/" + "root/"),
    "private IP": re.compile(r"\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    "GitHub token": re.compile("gh" + r"[pousr]_[A-Za-z0-9]{20,}"),
    "API key": re.compile("sk" + r"-[A-Za-z0-9_-]{20,}|AK" + r"IA[0-9A-Z]{16}"),
    "private key": re.compile("-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----"),
}
# Text files may name these on purpose (placeholders in docs).
ALLOW_LINES = re.compile(r"hygiene-scan: allow")


def tracked(root: pathlib.Path) -> list[pathlib.Path]:
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return all_files(root)
    return [root / p for p in out.decode().split("\0") if p]


def all_files(root: pathlib.Path) -> list[pathlib.Path]:
    return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts]


def scan_file(path: pathlib.Path, rel: str) -> list[str]:
    found = []
    if path.suffix.lower() in BLOCKED:
        found.append(f"{rel}: blocked type {path.suffix}")
    size = path.stat().st_size
    if size > MAX_BYTES:
        found.append(f"{rel}: {size} bytes, over {MAX_BYTES}")
    data = path.read_bytes()
    if b"\0" in data:
        found.append(f"{rel}: binary content")
        return found
    text = data.decode("utf-8", "replace")
    for n, line in enumerate(text.splitlines(), 1):
        if ALLOW_LINES.search(line):
            continue
        for name, pat in PATTERNS.items():
            if pat.search(line):
                found.append(f"{rel}:{n}: {name}")
    return found


def scan(root: pathlib.Path, every: bool = False) -> list[str]:
    files = all_files(root) if every else tracked(root)
    findings = []
    for p in sorted(files):
        if p.is_file():
            findings += scan_file(p, p.relative_to(root).as_posix())
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    files = all_files(root) if a.all else tracked(root)
    findings = scan(root, a.all)
    for f in findings:
        print(f)
    print(f"hygiene scan: {len(files)} files, {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
