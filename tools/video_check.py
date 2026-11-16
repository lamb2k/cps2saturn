#!/usr/bin/env python3
"""Video check: does the kit draw a CPS-1 / CPS-Dash picture exactly as MAME does?

capture  runs MAME with mame/video_frames.lua: a golden run (golden.lua, delta) plus, at the chosen frames, MAME's
         picture, palette, GFX RAM and CPS-A / CPS-B registers, and its graphics region. --off switches layers off
         in MAME (cleared enable bits in the game's writes to layer control or video control) to isolate them:
           scrolls                 every scroll layer off: sprites only
           scroll1,scroll2,...     those layers off; scroll2 and scroll3 go off by their video control bits,
                                   scroll1 by its enable mask (refused when another layer on shares the mask)
compare  draws each captured frame with the kit's own pieces (cps_video.py: scroll maps, row scroll, layer order,
         priority masks; cps_objects.py and the game's mapper for sprites, from the golden's object table) and
         compares it with MAME's picture pixel for pixel (lookdiff). Colours come from MAME's palette, so this checks
         what is drawn where, not palette conversion.

Config (per game, from your own work): video.layer_control and video.priority (CPS-B register offsets) and
video.layer_enable_masks (the three scroll layer enable masks), as the game's CPS-B setup gives them;
graphics.mapper; video.cps_a / video.cps_b override the board's register addresses.

usage:
  video_check.py capture --config C --name NAME --frames F,F,... [--off LAYERS] [--last N] [--out-root DIR]
                         [--dry-run]
  video_check.py compare RUN_DIR --config C [--offset K] [--search] [--out DIR] [--max-pct 0]
Sprites come from record (IRQs seen at the end of the frame) - 1 - offset. --search tries offsets 0..3 and
reports each; pick one, then gate with it. Pick frames where things move: a still screen passes at any offset.
Exit 0 pass, 1 a frame over --max-pct, 2 bad input. Everything written is derived from the game: keep it out of git.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boards  # noqa: E402
import cfg  # noqa: E402
import cps_objects  # noqa: E402
import cps_tiles  # noqa: E402
import cps_video  # noqa: E402
import golden_reader  # noqa: E402
import lookdiff  # noqa: E402
import mame_golden_run  # noqa: E402

SCROLLS = ("scroll1", "scroll2", "scroll3")


def game_video(c: dict) -> dict:
    v = dict(layer_control=cfg.get(c, "video.layer_control"), priority=cfg.get(c, "video.priority"),
             layer_enable_masks=cfg.get(c, "video.layer_enable_masks"))
    if v["layer_control"] is None or not v["layer_enable_masks"] or len(v["layer_enable_masks"]) != 3:
        sys.exit("config needs video.layer_control and video.layer_enable_masks (three masks), from the game's "
                 "CPS-B setup")
    if not v["priority"] or len(v["priority"]) != 4:
        sys.exit("config needs video.priority: the four CPS-B priority register offsets")
    return v


def off_taps(c: dict, off: str | None) -> dict:
    """Environment for the layer and video control taps that switch the --off layers off in MAME."""
    if not off:
        return {}
    v = game_video(c)
    masks = v["layer_enable_masks"]
    names = set(SCROLLS) if off == "scrolls" else {s.strip() for s in off.split(",")}
    if names - set(SCROLLS):
        sys.exit(f"--off: unknown {sorted(names - set(SCROLLS))}; use scrolls or {', '.join(SCROLLS)}")
    lc = vc = 0
    if names == set(SCROLLS):
        lc = masks[0] | masks[1] | masks[2]
    else:
        if "scroll2" in names:
            vc |= 0x04
        if "scroll3" in names:
            vc |= 0x08
        if "scroll1" in names:
            kept = [masks[i] for i, n in enumerate(SCROLLS) if n not in names]
            if any(masks[0] & k for k in kept):
                sys.exit("--off scroll1: its enable mask is shared with a layer that stays on")
            lc = masks[0]
    env = {}
    if lc:
        env["CPS2SAT_LAYER_CTRL"] = f"{boards.cps_b(c) + v['layer_control']:#x},{lc:#x}"
    if vc:
        env["CPS2SAT_VIDEO_CTRL"] = f"{boards.cps_a(c) + cps_video.VIDEOCONTROL:#x},{vc:#x}"
    return env


def capture(a) -> int:
    c = cfg.load(a.config)
    game_video(c)
    frames = sorted({int(f) for f in a.frames.split(",")})
    if frames[-1] >= a.last:
        sys.exit(f"--last {a.last} must be after the last frame {frames[-1]}")
    root = a.out_root or pathlib.Path(cfg.get(c, "paths.work") or ".") / "video_check"
    cmd, env, out = mame_golden_run.build(c, a.name, root, None, str(a.last), None, True, a.last + 100)
    cmd[-1] = str(HERE / "mame" / "video_frames.lua")
    env.update({
        "CPS2SAT_GOLDEN_LUA": (HERE / "mame" / "golden.lua").as_posix(),
        "CPS2SAT_FRAMES": ",".join(map(str, frames)),
        "CPS2SAT_FRAMES_DIR": (out / "frames").as_posix(),
        "CPS2SAT_GFX_RAM": f"{boards.value(c, 'gfx_ram'):#x},{cps_video.GFX_RAM_SIZE:#x}",
        "CPS2SAT_GFX_OUT": (out / "gfx.bin").as_posix(),
        "CPS2SAT_GFX_REGION": cfg.get(c, "graphics.region") or ":gfx",
    })
    env.update(off_taps(c, a.off))
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
                                                       off=a.off or "", delta=True), indent=1))
    with open(out / "stdout.txt", "w") as log:
        r = subprocess.run(cmd, env=dict(os.environ, **env), stdout=log, stderr=subprocess.STDOUT, timeout=a.timeout)
    got = len(read_frames(out)[1]) if (out / "frames" / "frames.txt").exists() else 0
    print("exit", r.returncode, "frames", got, "of", len(frames), "->", out)
    return r.returncode if got == len(frames) else 1


def read_frames(run: pathlib.Path) -> tuple[str, list[tuple[int, int, int, int]]]:
    lines = (run / "frames" / "frames.txt").read_text().split("\n")
    return lines[0].split()[1], [tuple(int(v) for v in l.split()) for l in lines[1:] if l.strip()]


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
    return [bytes(((v >> 16) & 255, (v >> 8) & 255, v & 255)) for v in struct.unpack(f">{len(raw) // 4}I", raw)]


def kit_picture(run: pathlib.Path, frame: int, objects: bytes, gfx: bytes, game: dict, g: dict, mapper):
    cps_a, cps_b = cps_video.regs((run / "frames" / f"f{frame:05d}.regs").read_bytes())
    f = cps_video.Frame((run / "frames" / f"f{frame:05d}.gfx").read_bytes(), cps_a, cps_b, game, gfx, mapper)
    pal = palette(run, frame)
    pix = cps_video.render(f, objects, g)
    return cps_video.W, cps_video.H, b"".join(pal[i] for i in pix)


def compare(a) -> int:
    c = cfg.load(a.config)
    g = cps_objects.geometry(c)
    if g["format"] != "cps1":
        sys.exit("video_check draws CPS-1 / CPS-Dash video only")
    game = game_video(c)
    mapper = cps_tiles.mapper_from(c)
    run = a.run
    manifest = json.loads((run / "manifest.json").read_text())
    order, frames = read_frames(run)
    gfx = (run / "gfx.bin").read_bytes()
    _, ws, osz = golden_reader.sizes(c)
    offsets = range(4) if a.search else [a.offset]
    need = {irq - 1 - k for _, irq, _, _ in frames for k in offsets}
    tables = {n: img[ws:ws + osz] for n, _, img in
              golden_reader.records(run / "golden.bin", ws, osz, manifest.get("delta", True)) if n in need}
    print(f"run {run.name}: layers off: {manifest.get('off') or 'none'}")
    for k in offsets:
        fails, worst = 0, 0.0
        for frame, irq, w, h in frames:
            rec = irq - 1 - k
            if rec not in tables:
                print(f"offset {k} frame {frame}: no record {rec}")
                fails += 1
                continue
            mame = mame_picture(run, frame, w, h, order)
            kit = kit_picture(run, frame, tables[rec], gfx, game, g, mapper)
            r = lookdiff.diff(mame, kit, threshold=0)
            ok = r["pct"] <= a.max_pct
            fails += not ok
            worst = max(worst, r["pct"])
            if not a.search or not ok:
                print(f"offset {k} frame {frame} record {rec}: {r['changed']} px differ ({r['pct']:.3f}%)"
                      + (f" box {r['bbox']}" if r["bbox"] else ""))
            if a.out:
                d = a.out / f"offset{k}"
                for sub, img in (("mame", mame), ("kit", kit)):
                    (d / sub).mkdir(parents=True, exist_ok=True)
                    lookdiff.write_png(d / sub / f"f{frame:05d}.png", *img)
                if not ok:
                    (d / "diff").mkdir(exist_ok=True)
                    lookdiff.write_png(d / "diff" / f"f{frame:05d}.png", *lookdiff.diff_image(mame, kit, r))
        print(f"offset {k}: {len(frames) - fails} of {len(frames)} frames pass, worst {worst:.3f}%")
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
    p.add_argument("--off", help="scrolls, or a comma list of scroll1, scroll2, scroll3")
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
