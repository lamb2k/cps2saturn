#!/usr/bin/env python3
"""Sprite-layer check: does the kit draw a CPS-1 / CPS-Dash sprite layer exactly as MAME does?

capture  runs MAME with mame/sprite_frames.lua: a golden run (golden.lua, delta) plus, at the chosen frames, MAME's
         screen with the scroll layers switched off (sprites only), its sprite palette, and its graphics region.
compare  draws each captured frame from the golden's object table with the kit's own pieces (cps_objects.py
         decode, the game's cps_tiles.Mapper, planar tiles from the graphics region, first entry on top) and
         compares it with MAME's picture pixel for pixel (lookdiff). Colours come from MAME's palette, so this
         checks positions, tiles, flips, blocks, mapping, ordering and the dumped table, not palette conversion.

Config (per game, from your own work): video.layer_control (CPS-B register offset of layer control) and
video.layer_enable_mask (its scroll layer enable bits), graphics.mapper; video.cps_b overrides the board's CPS-B
address. Flip screen is not handled.

usage:
  sprite_check.py capture --config C --name NAME --frames F,F,... [--last N] [--out-root DIR] [--dry-run]
  sprite_check.py compare RUN_DIR --config C [--offset K] [--search] [--out DIR] [--max-pct 0]
Record for frame f = (IRQs seen at the end of frame f) - 1 - offset. --search tries offsets 0..3 and reports each;
pick one, then gate with it. Exit 0 pass, 1 a frame over --max-pct, 2 bad input.
Everything written is derived from the game. Keep it outside git.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boards  # noqa: E402
import cfg  # noqa: E402
import cps_objects  # noqa: E402
import cps_tiles  # noqa: E402
import golden_reader  # noqa: E402
import lookdiff  # noqa: E402
import mame_golden_run  # noqa: E402

PENS = 0x200          # sprite palette page: colour bank * 16 + pen
TRANSPARENT = 15


def layer_control(c: dict) -> str:
    reg = cfg.get(c, "video.layer_control")
    mask = cfg.get(c, "video.layer_enable_mask")
    if reg is None or not mask:
        sys.exit("config needs video.layer_control and video.layer_enable_mask (from the game's CPS-B setup)")
    return f"{boards.cps_b(c) + reg:#x},{mask:#x}"


def capture(a) -> int:
    c = cfg.load(a.config)
    frames = sorted({int(f) for f in a.frames.split(",")})
    if frames[-1] >= a.last:
        sys.exit(f"--last {a.last} must be after the last frame {frames[-1]}")
    root = a.out_root or pathlib.Path(cfg.get(c, "paths.work") or ".") / "sprite_check"
    cmd, env, out = mame_golden_run.build(c, a.name, root, None, str(a.last), None, True, a.last + 100)
    cmd[-1] = str(HERE / "mame" / "sprite_frames.lua")
    env.update({
        "CPS2SAT_GOLDEN_LUA": (HERE / "mame" / "golden.lua").as_posix(),
        "CPS2SAT_LAYER_CTRL": layer_control(c),
        "CPS2SAT_FRAMES": ",".join(map(str, frames)),
        "CPS2SAT_FRAMES_DIR": (out / "frames").as_posix(),
        "CPS2SAT_GFX_OUT": (out / "gfx.bin").as_posix(),
        "CPS2SAT_GFX_REGION": cfg.get(c, "graphics.region") or ":gfx",
    })
    if a.dry_run:
        for k, v in env.items():
            print(f"{k}={v}")
        print(" ".join(f'"{x}"' if " " in x else x for x in cmd))
        return 0
    if out.exists():
        sys.exit(f"{out} exists: not overwriting")
    (out / "frames").mkdir(parents=True)
    mame_golden_run.seed(c, out)
    (out / "manifest.json").write_text(json.dumps(dict(set=cfg.get(c, "game.set"), frames=frames, last=a.last,
                                                       delta=True), indent=1))
    with open(out / "stdout.txt", "w") as log:
        r = subprocess.run(cmd, env=dict(os.environ, **env), stdout=log, stderr=subprocess.STDOUT, timeout=a.timeout)
    got = len(read_frames(out)[1]) if (out / "frames" / "frames.txt").exists() else 0
    print("exit", r.returncode, "frames", got, "of", len(frames), "->", out)
    return r.returncode if got == len(frames) else 1


def read_frames(run: pathlib.Path) -> tuple[str, list[tuple[int, int, int, int]]]:
    lines = (run / "frames" / "frames.txt").read_text().split("\n")
    order = lines[0].split()[1]
    return order, [tuple(int(v) for v in l.split()) for l in lines[1:] if l.strip()]


def mame_picture(run: pathlib.Path, frame: int, w: int, h: int, order: str) -> tuple[int, int, bytes]:
    raw = (run / "frames" / f"f{frame:05d}.rgb").read_bytes()
    rgb = bytearray(w * h * 3)
    fmt = "<I" if order == "le" else ">I"
    for i in range(w * h):
        v = struct.unpack_from(fmt, raw, i * 4)[0]
        rgb[i * 3:i * 3 + 3] = bytes(((v >> 16) & 255, (v >> 8) & 255, v & 255))
    return w, h, bytes(rgb)


def palette(run: pathlib.Path, frame: int) -> list[bytes]:
    raw = (run / "frames" / f"f{frame:05d}.pal").read_bytes()
    out = []
    for i in range(PENS + 1):
        v = struct.unpack_from(">I", raw, i * 4)[0]
        out.append(bytes(((v >> 16) & 255, (v >> 8) & 255, v & 255)))
    return out


def render(obj: bytes, gfx: bytes, pal: list[bytes], g: dict, sprite_map) -> tuple[int, int, bytes]:
    """The sprite layer as the kit draws it: (w, h, rgb). pal: 0x200 sprite pens, then the background pen."""
    w, h = g["view_w"], g["view_h"]
    canvas = [PENS] * (w * h)                     # PENS indexes the background colour
    count = max(1, len(gfx) // 0x80)
    cache: dict[int, list[list[int]]] = {}
    drawn = [t for t, on in cps_objects.tiles(obj, g, sprite_map) if on]
    for t in reversed(drawn):                     # first entry ends on top
        code = t.code % count                     # MAME wraps a tile number past the region
        px = cache.get(code)
        if px is None:
            px = cache[code] = cps_tiles.pens(gfx, code * 0x80, 16, 16, 8)
        for y in range(16):
            sy = t.sy + y
            if not 0 <= sy < h:
                continue
            row = px[15 - y if t.fy else y]
            for x in range(16):
                sx = t.sx + x
                if 0 <= sx < w:
                    p = row[15 - x if t.fx else x]
                    if p != TRANSPARENT:
                        canvas[sy * w + sx] = t.bank * 16 + p
    return w, h, b"".join(pal[i] for i in canvas)


def compare(a) -> int:
    c = cfg.load(a.config)
    g = cps_objects.geometry(c)
    if g["format"] != "cps1":
        sys.exit("sprite_check draws the CPS-1 / CPS-Dash sprite format only")
    mapper = cps_tiles.mapper_from(c)
    sprite_map = (lambda code: mapper.map("sprites", code)) if mapper else None
    run = a.run
    manifest = json.loads((run / "manifest.json").read_text())
    order, frames = read_frames(run)
    gfx = (run / "gfx.bin").read_bytes()
    _, ws, osz = golden_reader.sizes(c)
    offsets = range(4) if a.search else [a.offset]
    need = {irq - 1 - k for _, irq, _, _ in frames for k in offsets}
    tables = {}
    for n, _, img in golden_reader.records(run / "golden.bin", ws, osz, manifest.get("delta", True)):
        if n in need:
            tables[n] = img[ws:ws + osz]
    worst = {}
    for k in offsets:
        fails = 0
        for frame, irq, w, h in frames:
            rec = irq - 1 - k
            if rec not in tables:
                print(f"offset {k} frame {frame}: no record {rec}")
                fails += 1
                continue
            mame = mame_picture(run, frame, w, h, order)
            kit = render(tables[rec], gfx, palette(run, frame), g, sprite_map)
            r = lookdiff.diff(mame, kit, threshold=0)
            ok = r["pct"] <= a.max_pct
            fails += not ok
            worst[k] = max(worst.get(k, 0.0), r["pct"])
            if not a.search or not ok:
                print(f"offset {k} frame {frame} record {rec}: {r['changed']} px differ ({r['pct']:.3f}%)"
                      + (f" box {r['bbox']}" if r["bbox"] else ""))
            if a.out:
                for sub, img in (("mame", mame), ("kit", kit)):
                    (a.out / f"offset{k}" / sub).mkdir(parents=True, exist_ok=True)
                    lookdiff.write_png(a.out / f"offset{k}" / sub / f"f{frame:05d}.png", *img)
                if not ok:
                    (a.out / f"offset{k}" / "diff").mkdir(exist_ok=True)
                    lookdiff.write_png(a.out / f"offset{k}" / "diff" / f"f{frame:05d}.png",
                                       *lookdiff.diff_image(mame, kit, r))
        print(f"offset {k}: {len(frames) - fails} of {len(frames)} frames pass, worst {worst.get(k, 100.0):.3f}%")
        if not a.search:
            return 0 if fails == 0 else 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("capture")
    p.add_argument("--config", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--frames", required=True)
    p.add_argument("--last", type=int, default=1300)
    p.add_argument("--out-root", type=pathlib.Path)
    p.add_argument("--timeout", type=int, default=3000)
    p.add_argument("--dry-run", action="store_true")
    q = sub.add_parser("compare")
    q.add_argument("run", type=pathlib.Path)
    q.add_argument("--config", required=True)
    q.add_argument("--offset", type=int, default=0)
    q.add_argument("--search", action="store_true")
    q.add_argument("--out", type=pathlib.Path)
    q.add_argument("--max-pct", type=float, default=0.0)
    a = ap.parse_args(argv)
    return capture(a) if a.cmd == "capture" else compare(a)


if __name__ == "__main__":
    sys.exit(main())
