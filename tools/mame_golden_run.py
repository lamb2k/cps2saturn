#!/usr/bin/env python3
"""Record a MAME golden from the per-game config, optionally playing a saved input route.

usage: mame_golden_run.py --config C --name NAME [--route ROUTE] [--last N] [--save F,F] [--delta]
                          [--maxirq N] [--out-root DIR] [--dry-run]
Output: OUT_ROOT/NAME/{golden.bin, golden.bin.io.txt, stdout.txt, nvram/, cfg/, sta/}. OUT_ROOT defaults to
paths.work/mame. Refuses to overwrite an existing NAME, and refuses to start under 4 GB free disk.
--dry-run prints the command and environment and exits.
Settings baselines: paths.nvram_baseline (EEPROM boards: CPS-2, CPS-Dash) is copied to nvram/<set>/, and
paths.cfg_baseline (DIP switch boards: CPS-1) is copied into cfg/. Both are optional folders.
On CPS-1 and CPS-Dash the object table moves with the CPS-A object base register (see tools/boards.py): golden.lua
follows it and writes golden.bin.obj.txt, one "irq base" line per change.
Output is derived from the game. Keep it outside git.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boards  # noqa: E402
import cfg  # noqa: E402


def build(c: dict, name: str, out_root: pathlib.Path, route: str | None, last: str | None, save: str | None,
          delta: bool, maxirq: int) -> tuple[list[str], dict, pathlib.Path]:
    out = out_root / name
    tap = cfg.get(c, "cpu.irq_tap")
    register = boards.object_table(c) == "register"
    # A register-placed table is dumped from the start of GFX RAM until the game first writes the base register.
    obj_base = boards.value(c, "gfx_ram") if register else cfg.get(c, "ram.object_base")
    env = {
        "CPS2SAT_OUT": (out / "golden.bin").as_posix(),
        "CPS2SAT_IRQ_TAP": f"{tap[0]:#x},{tap[1]:#x}",
        "CPS2SAT_IRQ_VECTOR": f"{cfg.get(c, 'cpu.irq_vector_pc'):#x}",
        "CPS2SAT_WORK": f"{cfg.get(c, 'ram.work_base'):#x},{cfg.get(c, 'ram.work_size'):#x}",
        "CPS2SAT_OBJ": f"{obj_base:#x},{boards.object_size(c):#x}",
        "CPS2SAT_IO": ";".join(f"{lo:#x}-{hi:#x}" for lo, hi in cfg.get(c, "ram.io_ranges", [])),
        "CPS2SAT_MAXIRQ": str(maxirq),
    }
    if register:
        env["CPS2SAT_OBJ_REG"] = f"{boards.cps_a(c):#x},{boards.value(c, 'object_align'):#x}"
    if delta:
        env["CPS2SAT_DELTA"] = "1"
    if route:
        env["CPS2SAT_ROUTE"] = pathlib.Path(route).resolve().as_posix()
        env["CPS2SAT_ROUTE_BITS"] = ";".join(f"{t}|{f}" for t, f in cfg.get(c, "inputs.route_bits", []))
    if last:
        env["CPS2SAT_LAST"] = str(last)
    if save:
        env["CPS2SAT_SAVE"] = save
    cmd = [cfg.get(c, "paths.mame_exe") or "mame", cfg.get(c, "game.set"),
           "-rompath", cfg.get(c, "paths.rompath") or ".",
           "-video", "none", "-sound", "none", "-nothrottle", "-skip_gameinfo", "-autoboot_delay", "0",
           # Host keys, mice and pads must not reach the game: the route is the only input.
           "-keyboardprovider", "none", "-mouseprovider", "none", "-joystickprovider", "none",
           "-lightgunprovider", "none",
           "-nvram_directory", str(out / "nvram"), "-cfg_directory", str(out / "cfg"),
           "-state_directory", str(out / "sta"), "-autoboot_script", str(HERE / "mame" / "golden.lua")]
    return cmd, env, out


def seed(c: dict, out: pathlib.Path) -> None:
    """Copy the settings baselines into a new run folder, so no earlier run's settings leak in."""
    base = cfg.get(c, "paths.nvram_baseline")
    if base:
        shutil.copytree(base, out / "nvram" / cfg.get(c, "game.set"))
    base = cfg.get(c, "paths.cfg_baseline")
    if base:
        shutil.copytree(base, out / "cfg")
    (out / "cfg").mkdir(exist_ok=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--route")
    ap.add_argument("--last")
    ap.add_argument("--save")
    ap.add_argument("--delta", action="store_true")
    ap.add_argument("--maxirq", type=int, default=30000)
    ap.add_argument("--out-root", type=pathlib.Path)
    ap.add_argument("--timeout", type=int, default=3000)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    c = cfg.load(a.config)
    root = a.out_root or pathlib.Path(cfg.get(c, "paths.work") or ".") / "mame"
    cmd, env, out = build(c, a.name, root, a.route, a.last, a.save, a.delta, a.maxirq)
    if a.dry_run:
        for k, v in env.items():
            print(f"{k}={v}")
        print(" ".join(f'"{x}"' if " " in x else x for x in cmd))
        return 0
    if out.exists():
        sys.exit(f"{out} exists: not overwriting")
    if shutil.disk_usage(root if root.exists() else pathlib.Path.cwd()).free < 4 << 30:
        sys.exit("under 4 GB free: not starting")
    out.mkdir(parents=True)
    seed(c, out)
    with open(out / "stdout.txt", "w") as log:
        r = subprocess.run(cmd, env=dict(os.environ, **env), stdout=log, stderr=subprocess.STDOUT, timeout=a.timeout)
    g = out / "golden.bin"
    irqs = (out / "golden.bin.io.txt").read_text().count("V\n") if (out / "golden.bin.io.txt").exists() else 0
    print("exit", r.returncode, "bytes", g.stat().st_size if g.exists() else 0, "IRQ", irqs)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
