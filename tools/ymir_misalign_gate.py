#!/usr/bin/env python3
"""Strict-emulator data misalignment gate for Saturn builds. Reads a log; contains no emulator code.

The lesson: an SH-2 raises an address error on a 16-bit access at an odd address and on a 32-bit access at an address that is not a
multiple of 4. Emulators allow both. Static checks (align_gate.py) find symbols and cast sites; this finds the accesses that really happen
while the game runs: a misaligned read froze a dialogue box on a console while every emulator ran it.

How: patch one copy of an emulator (the AvP project used Ymir, which is GPL-3.0, so that patch is not in this kit and is not described
beyond the log format) so that each SH-2 data access at an address that is not a multiple of its width appends one line, once per
distinct (CPU, PC, width, kind), to a log:
    READ SH2-M PC=060A128E addr=060A1292 32-bit
    WRITE SH2-S PC=0600C112 addr=0600D001 16-bit
The emulator still performs the access (a real SH-2 would fault), so the log is the only trace. A line whose addr equals its PC is the emulator's
own instruction fetch at a 2 mod 4 PC, not a data access: it is counted and filtered. Every other line is a data access and fails the gate,
unless its PC is on the reviewed allowlist.

usage:
  ymir_misalign_gate.py --check LOG [--allow FILE] [--expect-hits]
  ymir_misalign_gate.py --run --exe EXE --cmd-args "ARGS WITH {log}" --log LOG --secs N [--keys SCHEDULE] [--allow FILE]
      Starts the emulator with no window activation, posts the scheduled keys to its own window only (no SendInput, no focus change),
      stops it after N seconds, then checks LOG. SCHEDULE is 'G@15,J@62,...' (key letter @ second) and needs Windows; without keys it runs
      anywhere. The log path the patched emulator writes is its own business: pass the same path as --log; {log} in --cmd-args is replaced by it.
Allowlist: lines `PC reason` (PC in hex, as printed in the log; # comments allowed). The reason is required. An entry that matches no
line in the log is reported (the code it covered may be gone) but does not fail the gate.
--expect-hits: positive control. Run a build that reintroduces a known bad access: the gate must FAIL on it. With this flag a log with data
accesses passes (exit 0) and a clean log fails (exit 1): it proves the patched emulator writes the log at all.
Exit 0 clean (or, with --expect-hits, hits found), 1 data accesses found (or none with --expect-hits), 2 bad input or no log written.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time

LINE = re.compile(r"(READ|WRITE)\s+(\S+)\s+PC=([0-9A-Fa-f]+)\s+addr=([0-9A-Fa-f]+)\s+(\d+)-bit")


class BadInput(Exception):
    pass


def load_allow(path: str | None) -> dict[int, str]:
    allow: dict[int, str] = {}
    if not path:
        return allow
    try:
        text = pathlib.Path(path).read_text()
    except OSError as e:
        raise BadInput(f"cannot read allowlist {path}: {e}")
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        pc, _, reason = line.partition(" ")
        if not reason.strip():
            raise BadInput(f"{path}:{n}: an allowlist entry needs a reason after the PC")
        try:
            allow[int(pc, 16)] = reason.strip()
        except ValueError:
            raise BadInput(f"{path}:{n}: not a hex PC: {pc}")
    return allow


def parse(text: str) -> tuple[int, list[tuple[str, str, int, int, int]]]:
    """-> (instruction fetch lines filtered, data accesses as (kind, cpu, pc, addr, bits))."""
    fetch, data = 0, []
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        kind, cpu, pc, addr, bits = m.groups()
        pc_i, addr_i = int(pc, 16), int(addr, 16)
        if pc_i == addr_i:
            fetch += 1
            continue
        data.append((kind, cpu, pc_i, addr_i, int(bits)))
    return fetch, data


def check(path: str, allow: dict[int, str], expect_hits: bool = False, out=None) -> int:
    out = out or sys.stdout
    try:
        text = pathlib.Path(path).read_text(errors="replace")
    except OSError as e:
        raise BadInput(f"cannot read log {path}: {e}")
    fetch, data = parse(text)
    hits = [d for d in data if d[2] not in allow]
    used = {d[2] for d in data if d[2] in allow}
    print(f"ymir misalign log {path}: {fetch} instruction fetch artefacts (filtered), {len(data)} data accesses, "
          f"{len(data) - len(hits)} allowed, {len(hits)} hits", file=out)
    for kind, cpu, pc, addr, bits in hits[:40]:
        print(f"  DATA {kind} {cpu} PC={pc:08X} addr={addr:08X} {bits}-bit", file=out)
    if len(hits) > 40:
        print(f"  ... {len(hits) - 40} more", file=out)
    for pc in sorted(set(allow) - used):
        print(f"  STALE allowlist PC {pc:08X}: no matching line ({allow[pc]})", file=out)
    if expect_hits:
        print("positive control: " + ("found data accesses, the log works" if hits else "NO data accesses found: the patched emulator wrote nothing useful"), file=out)
        return 0 if hits else 1
    return 1 if hits else 0


def run(exe: str, cmd_args: str, log: str, secs: float, keys: str) -> None:
    """Start the emulator, post the scheduled keys to its own window, stop it after secs."""
    sched = sorted((float(k.split("@")[1]), k.split("@")[0]) for k in keys.split(",") if k)
    if sched and os.name != "nt":
        raise BadInput("--keys needs Windows (posted window messages)")
    if os.path.exists(log):
        try:
            os.remove(log)
        except OSError:
            pass   # another emulator still holds it open; the patched emulator truncates the file when this run first logs it
    parts = shlex.split(cmd_args.replace("{log}", log), posix=(os.name != "nt"))   # Windows paths keep their backslashes, so split without POSIX escapes
    args = [exe, *[p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p for p in parts]]
    kw = {}
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= 1
        si.wShowWindow = 4   # SW_SHOWNOACTIVATE: the owner's keyboard and focus stay theirs
        kw["startupinfo"] = si
    pr = subprocess.Popen(args, cwd=os.path.dirname(os.path.abspath(exe)) or None, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, **kw)
    u = windows = None
    if sched:
        import ctypes
        import ctypes.wintypes as w
        u = ctypes.WinDLL("user32")

        def windows(pid):
            res = []

            @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
            def cb(h, _):
                p = w.DWORD()
                u.GetWindowThreadProcessId(h, ctypes.byref(p))
                if p.value == pid and u.IsWindowVisible(h):
                    r = w.RECT()
                    u.GetWindowRect(h, ctypes.byref(r))
                    res.append((h, r.right - r.left))
                return True
            u.EnumWindows(cb, 0)
            return [x for x in res if x[1] > 200]
    t0 = time.time()
    try:
        while time.time() - t0 < secs and pr.poll() is None:
            time.sleep(0.5)
            t = time.time() - t0
            if not sched:
                continue
            ws = windows(pr.pid)
            h = max(ws, key=lambda x: x[1])[0] if ws else None
            while sched and sched[0][0] <= t and h:
                u.PostMessageW(h, 0x7, 0, 0)   # WM_SETFOCUS for SDL's own focus state, to its own window only
                _, k = sched.pop(0)
                vk = ord(k[0].upper())
                sc = u.MapVirtualKeyW(vk, 0)
                u.PostMessageW(h, 0x100, vk, 1 | (sc << 16))
                time.sleep(0.12)
                u.PostMessageW(h, 0x101, vk, 1 | (sc << 16) | (3 << 30))
    finally:
        pr.terminate()
        time.sleep(1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", metavar="LOG")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--exe")
    ap.add_argument("--cmd-args", default="")
    ap.add_argument("--log")
    ap.add_argument("--secs", type=float, default=200)
    ap.add_argument("--keys", default="")
    ap.add_argument("--allow")
    ap.add_argument("--expect-hits", action="store_true")
    a = ap.parse_args(argv)
    try:
        allow = load_allow(a.allow)
        if a.run:
            if not (a.exe and a.log):
                raise BadInput("--run needs --exe and --log")
            run(a.exe, a.cmd_args, a.log, a.secs, a.keys)
            if not os.path.exists(a.log):
                print("no misalign log written: the patched emulator wrote nothing (the game did not boot, or this exe lacks the patch)", file=sys.stderr)
                return 2
            return check(a.log, allow, a.expect_hits)
        if a.check:
            return check(a.check, allow, a.expect_hits)
    except BadInput as e:
        print("bad input:", e, file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
