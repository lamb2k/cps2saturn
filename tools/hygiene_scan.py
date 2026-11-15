#!/usr/bin/env python3
"""Pre-push hygiene scan: no game material, no private paths, no secrets.

usage: hygiene_scan.py [ROOT] [--all | --history] [--allow-media PREFIX ...] [--allow-file FILE]
  ROOT           repository to scan (default: this repo)
  --all          scan every file under ROOT, not only the ones git tracks or would add
  --history      scan every blob reachable from any ref (`git rev-list --objects --all`), not the working tree:
                 a file that was committed and later deleted is still in the history and still gets published
  --allow-media  folder prefix (relative to ROOT, e.g. docs/media/) where owner-approved release media may live
  --allow-file   file of such prefixes, one per line, # comments (default: ROOT/.hygiene-media if present)

Checks, per file (or per blob in --history):
  - blocked types: ROMs, disc images, audio, images, save states, archives;
  - size over 512 KB;
  - binary content (NUL bytes) in any file;
  - private paths (drive-letter paths, home folders), private IPs, tokens and keys.
Allowed media folders: files there with a media suffix (png, jpg, jpeg, gif, webp, mp4, webm) skip the blocked-type,
size (up to 25 MB instead) and binary checks, so a game repo can keep approved screenshots and clips. Every other
type there (an iso, a zip, a wav) is still blocked, and text files there are still scanned.
In --history a blob shows once, under the first path git lists for it, as `path@blobid`.
Exit 0 when clean, 1 with a list of findings otherwise, 2 for bad input (not a git repository for --history).
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
MEDIA_OK = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".webm"}
MEDIA_MAX_BYTES = 25 * 1024 * 1024
ALLOW_FILE = ".hygiene-media"

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


def norm_prefixes(prefixes) -> list[str]:
    out = []
    for p in prefixes:
        p = p.strip().replace("\\", "/")
        while p.startswith("./"):
            p = p[2:]
        if p:
            out.append(p if p.endswith("/") else p + "/")
    return out


def load_allow(root: pathlib.Path, allow_file: str | None = None) -> list[str]:
    path = pathlib.Path(allow_file) if allow_file else root / ALLOW_FILE
    if not path.is_file():
        return []
    lines = [l.split("#", 1)[0] for l in path.read_text(encoding="utf-8").splitlines()]
    return norm_prefixes(lines)


def media_allowed(rel: str, allow) -> bool:
    return pathlib.PurePosixPath(rel).suffix.lower() in MEDIA_OK and any(rel.startswith(p) for p in allow)


def scan_text(data: bytes, rel: str) -> list[str]:
    """Binary and pattern checks on file content."""
    if b"\0" in data:
        return [f"{rel}: binary content"]
    found = []
    for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
        if ALLOW_LINES.search(line):
            continue
        for name, pat in PATTERNS.items():
            if pat.search(line):
                found.append(f"{rel}:{n}: {name}")
    return found


def scan_file(path: pathlib.Path, rel: str, allow=()) -> list[str]:
    if media_allowed(rel, allow):
        size = path.stat().st_size
        return [f"{rel}: {size} bytes, over {MEDIA_MAX_BYTES}"] if size > MEDIA_MAX_BYTES else []
    found = []
    if path.suffix.lower() in BLOCKED:
        found.append(f"{rel}: blocked type {path.suffix}")
    size = path.stat().st_size
    if size > MAX_BYTES:
        found.append(f"{rel}: {size} bytes, over {MAX_BYTES}")
    return found + scan_text(path.read_bytes(), rel)


def scan(root: pathlib.Path, every: bool = False, allow=()) -> list[str]:
    allow = norm_prefixes(allow)
    files = all_files(root) if every else tracked(root)
    findings = []
    for p in sorted(files):
        if p.is_file():
            findings += scan_file(p, p.relative_to(root).as_posix(), allow)
    return findings


def git(root: pathlib.Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], input=data, capture_output=True, check=True).stdout


def history_blobs(root: pathlib.Path):
    """[(blob id, path, size)] for every blob reachable from any ref, one entry per blob."""
    paths: dict[str, str] = {}
    for line in git(root, "rev-list", "--objects", "--all").decode("utf-8", "replace").splitlines():
        sha, _, path = line.partition(" ")
        paths.setdefault(sha, path)
    ids = list(paths)
    out = []
    checked = git(root, "cat-file", "--batch-check", data=("\n".join(ids) + "\n").encode()) if ids else b""
    for line in checked.decode().splitlines():
        sha, kind, size = line.split()
        if kind == "blob":
            out.append((sha, paths[sha], int(size)))
    return out


def scan_history(root: pathlib.Path, allow=()) -> tuple[int, list[str]]:
    """Scan every reachable blob. Returns (blobs scanned, findings)."""
    allow = norm_prefixes(allow)
    blobs = history_blobs(root)
    findings, to_read = [], []
    for sha, rel, size in blobs:
        tag = f"{rel}@{sha[:10]}"
        if media_allowed(rel, allow):
            if size > MEDIA_MAX_BYTES:
                findings.append(f"{tag}: {size} bytes, over {MEDIA_MAX_BYTES}")
            continue
        suffix = pathlib.PurePosixPath(rel).suffix.lower()
        if suffix in BLOCKED:
            findings.append(f"{tag}: blocked type {suffix}")
        if size > MAX_BYTES:
            findings.append(f"{tag}: {size} bytes, over {MAX_BYTES}")
        else:
            to_read.append((sha, tag))
    for i in range(0, len(to_read), 400):   # read contents in chunks to bound memory
        chunk = to_read[i:i + 400]
        buf = git(root, "cat-file", "--batch", data=("\n".join(s for s, _ in chunk) + "\n").encode())
        pos = 0
        for sha, tag in chunk:
            eol = buf.index(b"\n", pos)
            size = int(buf[pos:eol].split()[2])
            body = buf[eol + 1:eol + 1 + size]
            pos = eol + 1 + size + 1
            findings += scan_text(body, tag)
    return len(blobs), findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--allow-media", action="append", default=[], metavar="PREFIX")
    ap.add_argument("--allow-file")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    allow = norm_prefixes(a.allow_media) + load_allow(root, a.allow_file)
    if a.history:
        try:
            n, findings = scan_history(root, allow)
        except (OSError, subprocess.CalledProcessError):
            print("hygiene scan: not a git repository (or git is missing)", file=sys.stderr)
            return 2
        for f in findings:
            print(f)
        print(f"hygiene scan (history): {n} blobs, {len(findings)} findings")
        return 1 if findings else 0
    files = all_files(root) if a.all else tracked(root)
    findings = scan(root, a.all, allow)
    for f in findings:
        print(f)
    print(f"hygiene scan: {len(files)} files, {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
