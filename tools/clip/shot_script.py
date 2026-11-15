#!/usr/bin/env python3
"""Frame-exact clip capture from your own emulator copy: a route to the scene, then paused, one-frame-at-a-time takes.

Game-neutral. Every game constant (the vblank counter, the idle player-state bytes, the health word for staged holds,
the enemy-pool probe, the pad keys) comes from the `capture:` section of the per-game config
(see configs/avspu.example.yaml). The tool drives the emulator through tools/yaba_mcp.py. Nothing here uploads anything.

usage: shot_script.py --config CONFIG SPEC.json [--dry-run]
       shot_script.py --disclose OUT_DIR     print the staged assists of a capture, for caption disclosure

What it does
  1. Writes a few keys into the ini of YOUR OWN emulator copy (a folder that holds a marker file, see below), starts
     the emulator on the spec's disc without activating its window, and checks that its MCP port belongs to the
     process it started.
  2. Plays the route free-running, waiting on the game's own vblank counter and memory, never on wall time.
  3. Saves a state, then captures each take with the core paused: every picture is one emulated frame
     (framebuffer_burst), so host load cannot drop or repeat pictures. Each take reloads the saved state first.

Rules baked in
  - Writes only to the ini beside the emulator copy named in the config. The folder must hold an empty file named
    .capture-copy (you create it: it says "this copy is for captures"). The user's own settings folder is refused.
  - Never global input. Keys go to the emulator's own window handle (PostMessage) or through the bridge's pad tool.
  - Staged assists (a health hold) are allowed, listed in <out>/assists.json and in every take.json, and --disclose
    prints them, so captions can say what was staged.
  - Capture is silent by default (the core's sound off); sound is laid in later (tools/video/mix.py).
  - Frames and discs stay on this PC, out of git.

Spec (JSON)
  name       short tag for the window title
  cue        the disc image; elf (optional) the ELF of the same build, for "sym:NAME" addresses (needs capture.nm)
  out        folder for this shot: <out>/route/NN_label.png, <out>/<take id>/f000000.png, <out>/<take id>/take.json,
             <out>/capture.log, <out>/assists.json
  build      free text copied into take.json (commit, flags): the build the pictures came from
  window     [w, h] of the window while capturing (the same size for every clip keeps one crop)
  slot       emulator state slot saved when the route ends; each take reloads it. "slot_ready": true skips the
             save, so a retake can start from a state kept earlier
  route      list of steps (below), or {"repeat": N, "steps": [...]}
  takes      list of {id, frames, schedule: [[picture, [keys]], ...], chunk (10), pre_idle (0), health (value),
             probe_enemies, probe_player, reload (true)}
  wait_max_s wall-clock guard for one wait (240)
  sh2cache   false (default; recordings use the cache model off) or true for a labelled timing-comparison take

Route steps (strings; all waits count the game's own vblanks)
  w:N              wait until the vblank counter is at least N (counted from boot)
  r:N              wait N vblanks from now
  t:keys[:H[:G]]   tap keys (a+right ...) for H vblanks (default 8), then wait G vblanks (default 30)
  h:keys:N         hold keys for N vblanks, then release
  press:keys       press keys and leave them down until the next press: or release
  release          let every key up
  p:label          screenshot to <out>/route/NN_label.png (look at these to check the route landed)
  idle[:N]         wait up to N vblanks until the player is in one of capture.idle.states
  hp:N             write the health word once (a staged assist; logged)
  save:S / load:S  save or load the emulator state in slot S (pauses around it)
  step:N           pause, advance N frames, resume (paused one-frame stepping inside a route)
  ge:ADDR:MIN[:W]            wait until the W-byte (default 4) big-endian value at ADDR (hex) is at least MIN
  in:ADDR:LO:HI[:W]          wait until the value is between LO and HI, inclusive
  need0:ADDR:MASK[:W]        abort the capture (no frames) unless none of the MASK bits are set (read only)
  need1:ADDR:MASK[:W]        abort unless all of the MASK bits are set
  needeq:ADDR:VALUE[:W]      abort unless the value equals VALUE
  {"repeat": N, "steps": [...]}   run the steps N times
ADDR is hex, or "sym:NAME" / "sym:NAME+0x10" from the spec's ELF. The caller retries an aborted capture.
Key names are the keys of capture.keys. Take keys: `schedule` is [[picture, [keys held from there]], ...].
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Callable

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import cfg as cfgmod  # noqa: E402
import yaba_mcp  # noqa: E402

MARKER = ".capture-copy"


class CaptureAbort(RuntimeError):
    """A need condition failed or a guard tripped: no frames were captured."""


# ---------------------------------------------------------------- config

def _int(v: Any, what: str) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, str)):
        raise SystemExit(f"capture config: {what} must be a number (fill it from your own emulator work)")
    return int(v, 0) if isinstance(v, str) else v


def parse_addr(v: Any, symbols: dict[str, int] | None = None) -> int:
    """An address: a number, a hex string, or 'sym:NAME[+off]' looked up in the ELF's symbols."""
    if isinstance(v, int):
        return v
    s = str(v).strip()
    m = re.fullmatch(r"sym:([A-Za-z0-9_.$]+)(?:\+(0x[0-9a-fA-F]+|\d+))?", s)
    if m:
        if not symbols or m[1] not in symbols:
            raise SystemExit(f"symbol {m[1]} not found: give the spec an elf and set capture.nm")
        return symbols[m[1]] + (int(m[2], 0) if m[2] else 0)
    return int(s, 16) if not s.lower().startswith("0x") else int(s, 0)


def load_symbols(nm: str, elf: str) -> dict[str, int]:
    """name -> address from `nm ELF` (your target toolchain's nm)."""
    out = subprocess.run([nm, elf], capture_output=True, text=True).stdout
    syms: dict[str, int] = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 3:
            syms[p[2].lstrip("_")] = int(p[0], 16)
    return syms


def capture_settings(cfg: dict, need_game: bool = True) -> dict:
    """The capture: section with defaults, checked. need_game: the vblank counter must be set."""
    cap = dict(cfgmod.get(cfg, "capture", {}) or {})
    cap.setdefault("emulator_exe", "yabasanshiro.exe")
    cap.setdefault("ini_name", "yabause.ini")
    cap.setdefault("port", 9790)
    cap.setdefault("pad_mode", "window")
    cap.setdefault("keys", {})
    cap.setdefault("ini_extra", {})
    if cap["pad_mode"] not in ("window", "mcp"):
        raise SystemExit("capture.pad_mode must be window or mcp")
    if need_game:
        vb = cap.get("vblank") or {}
        if "addr" not in vb:
            raise SystemExit("capture.vblank.addr is not set: fill it from your own MAME/emulator work (see configs/avspu.example.yaml)")
    return cap


# ---------------------------------------------------------------- route language

NEEDS_ARG = {"w", "r", "t", "h", "press", "p", "hp", "save", "load", "step", "ge", "in", "need0", "need1", "needeq"}
NO_ARG = {"release", "idle"}


def parse_step(step: Any) -> tuple[str, list[str]]:
    if not isinstance(step, str):
        raise SystemExit(f"route step must be a string or a repeat block: {step!r}")
    k, _, a = step.partition(":")
    p = a.split(":") if a else []
    if k not in NEEDS_ARG and k not in NO_ARG:
        raise SystemExit("unknown route step " + step)
    if k in NEEDS_ARG and k != "press" and not p:
        raise SystemExit(f"route step needs an argument: {step}")
    return k, p


def validate_route(steps: list, depth: int = 0) -> int:
    """Check a route's syntax without running it. Returns the number of leaf steps."""
    n = 0
    for s in steps:
        if isinstance(s, dict):
            if set(s) - {"repeat", "steps"} or "steps" not in s or int(s.get("repeat", 1)) < 1 or depth > 4:
                raise SystemExit(f"bad repeat block: {s!r}")
            n += validate_route(s["steps"], depth + 1) * int(s.get("repeat", 1))
        else:
            parse_step(s)
            n += 1
    return n


# ---------------------------------------------------------------- pad

class McpPad:
    """Pad state through the bridge's pad_set tool (a patched emulator build). `codes` maps key names to the codes it takes."""

    def __init__(self, mcp: Any, codes: dict[str, int]) -> None:
        self.mcp, self.codes = mcp, codes
        self.down: set[str] = set()

    def set(self, names) -> None:
        names = set(names)
        for n in names:
            if n not in self.codes:
                raise SystemExit(f"key {n} is not in capture.keys")
        self.down = names
        self.mcp.call("pad_set", keys=sorted(self.codes[n] for n in names))


# ---------------------------------------------------------------- the shooter

class Shooter:
    """Runs a route and takes against an emulator object (Mcp-like: call, read, write) and a pad (set)."""

    def __init__(self, emu: Any, pad: Any, cap: dict, out: pathlib.Path, spec: dict, symbols: dict[str, int] | None = None,
                 log: Callable[..., None] = print, poll_s: float = 0.05, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.emu, self.pad, self.cap, self.out, self.spec = emu, pad, cap, pathlib.Path(out), spec
        self.symbols = symbols or {}
        self.log, self.poll_s, self.clock, self.sleep = log, poll_s, clock, sleep
        self.wait_max = float(spec.get("wait_max_s", 240))
        self.assists: list[dict] = []
        self.vb_addr = parse_addr(cap["vblank"]["addr"], self.symbols)
        self.vb_bytes = int(cap["vblank"].get("bytes", 4))

    # reads and waits ----------------------------------------------------
    def word(self, addr: int, nbytes: int = 4) -> int:
        return int.from_bytes(self.emu.read(addr, nbytes), "big")

    def vblank(self) -> int:
        return self.word(self.vb_addr, self.vb_bytes)

    def state_hex(self) -> str | None:
        idle = self.cap.get("idle")
        if not idle or "addr" not in idle:
            return None
        return self.emu.read(parse_addr(idle["addr"], self.symbols), int(idle.get("bytes", 1))).hex()

    def is_idle(self) -> bool:
        st = self.state_hex()
        states = [str(s).lower() for s in ((self.cap.get("idle") or {}).get("states") or [])]
        return st is not None and st in states

    def wait_until(self, target: int, what: str) -> bool:
        t0 = self.clock()
        while self.vblank() < target:
            if self.clock() - t0 > self.wait_max:
                self.log("TIMEOUT", what, "vblank", self.vblank(), "target", target)
                return False
            self.sleep(self.poll_s)
        return True

    def wait_value(self, addr: int, nbytes: int, ok: Callable[[int], bool], what: str) -> bool:
        t0 = self.clock()
        while not ok(self.word(addr, nbytes)):
            if self.clock() - t0 > self.wait_max:
                self.log("TIMEOUT", what)
                return False
            self.sleep(self.poll_s)
        return True

    # assists ------------------------------------------------------------
    def write_health(self, value: int) -> None:
        h = self.cap.get("health") or {}
        if "addr" not in h:
            raise SystemExit("capture.health.addr is not set: needed for a staged health hold")
        self.emu.write(parse_addr(h["addr"], self.symbols), int(value).to_bytes(int(h.get("bytes", 2)), "big"))

    def note_assist(self, **kw: Any) -> dict:
        kw["staged"] = True
        self.assists.append(kw)
        return kw

    def save_assists(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "assists.json").write_text(json.dumps(self.assists, indent=1))

    # route --------------------------------------------------------------
    def route(self, steps: list) -> None:
        (self.out / "route").mkdir(parents=True, exist_ok=True)
        self._run(steps, [0])

    def _run(self, steps: list, counter: list[int]) -> None:
        for s in steps:
            if isinstance(s, dict):
                for _ in range(int(s.get("repeat", 1))):
                    self._run(s["steps"], counter)
            else:
                self.step(s, counter[0])
                counter[0] += 1

    def _addr_args(self, p: list[str], n_before_width: int) -> tuple[int, list[int], int]:
        addr = parse_addr(p[0], self.symbols)
        nums = [int(x, 0) for x in p[1:1 + n_before_width]]
        width = int(p[1 + n_before_width]) if len(p) > 1 + n_before_width else 4
        return addr, nums, width

    def step(self, step: str, index: int = 0) -> None:
        k, p = parse_step(step)
        self.log("route", index, step)
        if k == "w":
            self.wait_until(int(p[0], 0), step)
        elif k == "r":
            self.wait_until(self.vblank() + int(p[0]), step)
        elif k in ("t", "h"):
            keys = [x for x in p[0].split("+") if x]
            hold = int(p[1]) if len(p) > 1 and p[1] else 8
            self.pad.set(keys)
            self.wait_until(self.vblank() + hold, step)
            self.pad.set([])
            if k == "t":
                self.wait_until(self.vblank() + (int(p[2]) if len(p) > 2 and p[2] else 30), step)
        elif k == "press":
            self.pad.set([x for x in (p[0] if p else "").split("+") if x])
        elif k == "release":
            self.pad.set([])
        elif k == "p":
            self.emu.call("framebuffer_screenshot", path=str(self.out / "route" / ("%02d_%s.png" % (index, p[0]))))
        elif k == "idle":
            end = self.vblank() + (int(p[0]) if p else 600)
            while self.vblank() < end and not self.is_idle():
                self.sleep(self.poll_s)
            self.log("idle: state", self.state_hex())
        elif k == "hp":
            self.write_health(int(p[0], 0))
            self.log(json.dumps(self.note_assist(kind="health_set", value=int(p[0], 0), at_vblank=self.vblank(), step=index)))
        elif k == "save":
            self.emu.call("pause")
            self.log(self.emu.call("save_state", slot=int(p[0]))[:120])
            self.emu.call("resume")
        elif k == "load":
            self.emu.call("pause")
            self.log(self.emu.call("load_state", slot=int(p[0]))[:120])
            self.sleep(0.5)
            self.emu.call("resume")
        elif k == "step":
            tmp = self.out / "_step"
            tmp.mkdir(parents=True, exist_ok=True)
            self.emu.call("pause")
            self.emu.call("framebuffer_burst", directory=str(tmp), frames=int(p[0]), prefix="x")
            shutil.rmtree(tmp, ignore_errors=True)
            self.emu.call("resume")
        elif k == "ge":
            addr, (lo,), w = self._addr_args(p, 1)
            self.wait_value(addr, w, lambda v: v >= lo, step)
        elif k == "in":
            addr, (lo, hi), w = self._addr_args(p, 2)
            self.wait_value(addr, w, lambda v: lo <= v <= hi, step)
        elif k in ("need0", "need1", "needeq"):
            addr, (arg,), w = self._addr_args(p, 1)
            val = self.word(addr, w)
            self.log(k, p[0], hex(val))
            bad = {"need0": val & arg != 0, "need1": val & arg != arg, "needeq": val != arg}[k]
            if bad:
                raise CaptureAbort("ABORT " + step)

    # takes --------------------------------------------------------------
    def take(self, t: dict, slot: int | None) -> dict:
        """Paused, one frame per picture. schedule = [[picture, [keys]], ...]; frames = how many pictures to keep."""
        emu = self.emu
        tdir = self.out / str(t["id"])
        tmp = tdir / "_burst"
        if tdir.exists():
            shutil.rmtree(tdir)
        tmp.mkdir(parents=True)
        emu.call("pause")
        if slot is not None and t.get("reload", True):
            emu.call("load_state", slot=slot)
            self.sleep(0.5)
        sched = sorted((int(f), list(k)) for f, k in t.get("schedule", [[0, []]]))
        total = int(t["frames"])
        chunk = int(t.get("chunk", 10))
        health = t.get("health")        # staged assist: the health word is put back before every chunk
        health_chunks = 0
        f = k = seg = 0
        keys: list[str] = []
        trace: list[dict] = []
        for pre in range(int(t.get("pre_idle", 0))):   # step unkeyed until the player stands free, so the take starts idle
            if self.is_idle():
                break
            emu.call("framebuffer_burst", directory=str(tmp), frames=1, prefix="pre%04d_" % pre)
        for x in tmp.glob("pre*"):
            x.unlink()
        while f < total:
            while k < len(sched) and sched[k][0] <= f:
                keys = sched[k][1]
                k += 1
            nxt = sched[k][0] if k < len(sched) else total
            n = max(1, min(chunk, nxt - f, total - f))
            self.pad.set(keys)
            if health:
                self.write_health(int(health))
                health_chunks += 1
            emu.call("framebuffer_burst", directory=str(tmp), frames=n, prefix="s%04d_" % seg)
            got = sorted(tmp.glob("s%04d_*.png" % seg))
            if len(got) != n:
                self.log("WARNING: asked", n, "frames, got", len(got))
            for j, g in enumerate(got):
                shutil.move(str(g), str(tdir / ("f%06d.png" % (f + j))))
            ent: dict[str, Any] = dict(f=f, n=len(got), keys=list(keys), vblank=self.vblank(), state=self.state_hex(),
                                       health_held=bool(health))
            ep = self.cap.get("enemy_pool")
            if t.get("probe_enemies") and ep:   # read only: each enemy block's health word, for picking kill moments
                base, cnt, stride = parse_addr(ep["base"], self.symbols), int(ep["count"]), int(ep["stride"])
                off, hb = int(ep.get("health_offset", 0)), int(ep.get("health_bytes", 2))
                blk = emu.read(base, cnt * stride)
                ent["enemy_hp"] = [int.from_bytes(blk[i * stride + off:i * stride + off + hb], "big") for i in range(cnt)]
            pb = self.cap.get("player_block")
            if t.get("probe_player") and pb:    # read only: the player block, to find counters
                ent["player_blk"] = emu.read(parse_addr(pb["base"], self.symbols), int(pb["size"])).hex()
            trace.append(ent)
            f += max(len(got), 1)
            seg += 1
            if seg % 10 == 0:
                self.log("take", t["id"], f, "/", total)
        self.pad.set([])
        shutil.rmtree(tmp, ignore_errors=True)
        assists = []
        if health:
            assists.append(self.note_assist(kind="health_hold", value=int(health), chunks=health_chunks, take=t["id"]))
        data = dict(take=t, frames=f, build=self.spec.get("build"), assists=assists, staged=bool(assists),
                    disclose=[assist_text(a) for a in assists], trace=trace)
        (tdir / "take.json").write_text(json.dumps(data, indent=1))
        self.log("take", t["id"], "done:", f, "frames in", tdir)
        return data

    def run(self) -> None:
        """The whole spec: route, state save, takes."""
        self.out.mkdir(parents=True, exist_ok=True)
        slot = self.spec.get("slot")
        try:
            if self.spec.get("route"):
                self.route(self.spec["route"])
        except CaptureAbort as e:
            self.log(str(e))
            (self.out / "ABORTED").write_text(str(e))
            self.save_assists()
            raise
        if self.spec.get("takes"):
            if slot is not None and not self.spec.get("slot_ready"):
                self.emu.call("pause")
                self.log(self.emu.call("save_state", slot=int(slot))[:120])
            for t in self.spec["takes"]:
                self.take(t, slot)
        self.save_assists()
        self.log("capture done")


def assist_text(a: dict) -> str:
    """One plain sentence for a caption or a hand-back."""
    if a.get("kind") == "health_hold":
        return f"Player health was held at {a['value']} during take {a.get('take')} (staged)."
    if a.get("kind") == "health_set":
        return f"Player health was set to {a['value']} once during the route (staged)."
    return "A staged assist was used: " + json.dumps(a, sort_keys=True)


def disclosures(out_dir: str | os.PathLike) -> list[str]:
    """Every staged assist found in a capture folder (assists.json and each take.json), as plain sentences."""
    out = pathlib.Path(out_dir)
    lines: list[str] = []
    p = out / "assists.json"
    if p.exists():
        lines += [assist_text(a) for a in json.loads(p.read_text())]
    return sorted(set(lines))


# ---------------------------------------------------------------- launching (own copy only)

def check_own_copy(emu_dir: pathlib.Path, ini: pathlib.Path) -> None:
    appdata = os.environ.get("APPDATA", "")
    if appdata and pathlib.Path(appdata).resolve() in emu_dir.resolve().parents:
        raise SystemExit(f"{emu_dir} is inside the user's settings folder. Use your own emulator copy.")
    if not (emu_dir / MARKER).exists():
        raise SystemExit(f"{emu_dir} has no {MARKER} file. Capture only runs an emulator copy made for it: copy the emulator "
                         f"folder, put an empty {MARKER} file in it, and point capture.emulator_dir there.")
    if ini.resolve().parent != emu_dir.resolve():
        raise SystemExit(f"ini {ini} is not beside the emulator in {emu_dir}")


def ini_changes(cap: dict, spec: dict) -> dict[str, str]:
    want = {
        r"Debug\McpServerPort": str(cap["port"]),
        r"Debug\McpServerEnabled": "true",
        r"General\UseSh2Cache": "true" if spec.get("sh2cache") else "false",
        r"General\CdRomISO": str(spec["cue"]).replace("\\", "/"),
        r"Sound\SoundCore": str(cap.get("sound_core", 0)),
        "autostart": "true",
    }
    want.update({str(k): str(v) for k, v in (cap.get("ini_extra") or {}).items()})
    return want


def patch_ini(text: str, want: dict[str, str], ini_name: str = "ini") -> str:
    for k, v in want.items():
        if not re.search(rf"(?m)^{re.escape(k)}=", text):
            raise SystemExit(f"{ini_name}: no {k} line (start the emulator once so it writes its settings)")
        text = re.sub(rf"(?m)^{re.escape(k)}=.*$", lambda _m, k=k, v=v: k + "=" + v, text)
    return text


def _win(hwnd: int, w: int | None = None, h: int | None = None, title: str | None = None) -> None:
    """Resize and label our own window without activating it (SWP_NOACTIVATE | SWP_NOZORDER | SWP_NOMOVE)."""
    import ctypes
    u = ctypes.windll.user32
    u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    if title:
        u.SetWindowTextW(ctypes.c_void_p(hwnd), title)
    if w and h:
        u.SetWindowPos(ctypes.c_void_p(hwnd), None, 0, 0, int(w), int(h), 0x0010 | 0x0004 | 0x0002)
        time.sleep(1.0)


def _to_back(hwnd: int) -> None:
    """Keep the window shown and at the bottom of the stacking order, never activated."""
    import ctypes
    u = ctypes.windll.user32
    u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    for _ in range(10):
        u.ShowWindow(ctypes.c_void_p(hwnd), 4)       # SW_SHOWNOACTIVATE
        u.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(1), 0, 0, 0, 0, 0x0013)   # HWND_BOTTOM, NOSIZE|NOMOVE|NOACTIVATE
        time.sleep(0.5)
        if not u.IsIconic(ctypes.c_void_p(hwnd)):
            break


def start_emulator(emu_exe: pathlib.Path) -> subprocess.Popen:
    kw: dict[str, Any] = {}
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4     # SW_SHOWNOACTIVATE: visible, not activated (a minimised window never paints)
        kw = dict(startupinfo=si, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    return subprocess.Popen([str(emu_exe)], cwd=str(emu_exe.parent), **kw)


def key_table(cap: dict) -> dict[str, int]:
    return {str(k): _int(v, f"capture.keys.{k}") for k, v in (cap.get("keys") or {}).items()}


def run_capture(cfg: dict, spec: dict, dry_run: bool = False) -> int:
    cap = capture_settings(cfg)
    emu_dir_s = cap.get("emulator_dir")
    if not emu_dir_s:
        raise SystemExit("capture.emulator_dir is not set (the folder of your own emulator copy)")
    emu_dir = pathlib.Path(emu_dir_s)
    ini = emu_dir / cap["ini_name"]
    exe = emu_dir / cap["emulator_exe"]
    check_own_copy(emu_dir, ini)
    n = validate_route(spec.get("route", []))
    want = ini_changes(cap, spec)
    if dry_run:
        print(f"emulator: {exe}\nini: {ini}")
        for k, v in want.items():
            print(f"  ini {k}={v}")
        print(f"route steps: {n}; takes: {len(spec.get('takes', []))}; pad: {cap['pad_mode']}; out: {spec['out']}")
        return 0
    if not pathlib.Path(spec["cue"]).exists():
        raise SystemExit(f"cue not found: {spec['cue']}")
    symbols: dict[str, int] = {}
    if spec.get("elf") and cap.get("nm"):
        symbols = load_symbols(str(cap["nm"]), str(spec["elf"]))
    ini.write_bytes(patch_ini(ini.read_bytes().decode("latin-1"), want, ini.name).encode("latin-1"))
    out = pathlib.Path(spec["out"])
    out.mkdir(parents=True, exist_ok=True)
    port = int(cap["port"])
    proc = start_emulator(exe)
    log_f = open(out / "capture.log", "a", buffering=1)

    def log(*a: Any) -> None:
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), " ".join(str(x) for x in a))
        print(line, flush=True)
        log_f.write(line + "\n")

    rc = 0
    try:
        m = yaba_mcp.Mcp(f"http://127.0.0.1:{port}/mcp")
        t0 = time.time()
        while True:
            try:
                m.initialize()
                break
            except Exception:
                if time.time() - t0 > 120:
                    raise
                time.sleep(0.3)
        owner = yaba_mcp.port_owner(port)
        if owner != proc.pid:
            log(f"port {port} belongs to pid {owner}, not the emulator started here ({proc.pid}); this capture did not run")
            return 3
        log("tools", m.list_tools())
        keys = key_table(cap)
        wp = yaba_mcp.WindowPad(proc.pid, keys) if os.name == "nt" else None
        if wp is not None:
            _to_back(wp.hwnd)
            _win(wp.hwnd, title=f"CAPTURE: {spec.get('name', 'clip')} [port {port}]")   # every emulator window we open is labelled
            if spec.get("window"):
                _win(wp.hwnd, *spec["window"])
        pad: Any = McpPad(m, keys) if cap["pad_mode"] == "mcp" else wp
        if pad is None:
            raise SystemExit("window pad input needs Windows; use capture.pad_mode: mcp with a patched emulator")
        sh = Shooter(m, pad, cap, out, spec, symbols, log=log)
        t_start = time.time()
        while sh.vblank() == 0 and time.time() - t_start < 120:   # the core is not up yet
            time.sleep(0.5)
        try:
            sh.run()
        except CaptureAbort:
            rc = 4
    finally:
        log_f.close()
        proc.terminate()      # only the process this run started
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", nargs="?", help="capture spec JSON")
    ap.add_argument("--config", help="per-game config (YAML) with a capture: section")
    ap.add_argument("--dry-run", action="store_true", help="check the spec, print the ini changes, start nothing")
    ap.add_argument("--disclose", metavar="OUT_DIR", help="print the staged assists of a capture folder")
    a = ap.parse_args(argv)
    if a.disclose:
        print("\n".join(disclosures(a.disclose)))
        return 0
    if not (a.spec and a.config):
        ap.error("SPEC and --config are required")
    spec = json.loads(pathlib.Path(a.spec).read_text(encoding="utf-8"))
    return run_capture(cfgmod.load(a.config), spec, dry_run=a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
