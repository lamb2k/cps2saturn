#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Screen-fixed objects against a cropped view: fail when the crop cuts one.

The lesson: a port that shows less of the original picture than the arcade or console drew (a 352 wide view of a 384 wide
picture, a 4:3 safe area of a 16:9 frame, an overscan crop) cuts everything near the edges. The world may be cropped; the
objects that are fixed to the screen (health bars, portraits, timers, prompts, text) must stay whole. This tool takes the
objects of each frame, as the port draws them (after any shift the port applies), and the crop, and reports every
screen-fixed object that is partly or wholly outside the visible window.

Input: JSON lines, one frame per line:  {"frame": 1234, "mode": 8, "objs": [[x, y, w, h, fixed], ...]}
  x, y, w, h  the rectangle the object is drawn at, in the source picture's coordinates (left edge x, top edge y, pixels)
  fixed       1 when the port's rule calls the object screen-fixed, 0 for world objects (they are not checked)
  "mode" is optional and only copied into the report. Objects with w or h of 0 are ignored.
The visible window is [crop_left, width - crop_right) horizontally and, with --height, [crop_top, height - crop_bottom) vertically.

usage: screenfix_check.py FRAMES.jsonl --width W --crop C [--crop-right C2] [--height H --crop-top T --crop-bottom B] [--max-report N] [--json OUT]
       screenfix_check.py --selftest
exit 0: no screen-fixed object clipped; 1: at least one; 2: bad input.
Any port can use it: list the screen-fixed objects per frame (from the original game's object list and your rule), apply your shift, run this.
Stdlib only."""
import argparse, json, sys


def check_frame(objs, width, cl, cr, height=None, ct=0, cb=0):
    """-> list of (index, x, y, w, h, side) for every fixed object not fully inside the window; side 'left', 'right', 'top', 'bottom' or 'outside'"""
    lo, hi = cl, width - cr
    bad = []
    for i, o in enumerate(objs):
        x, y, w, h, fx = o[:5]
        if not fx or w <= 0 or h <= 0: continue
        sides = []
        if x < lo: sides.append("left")
        if x + w > hi: sides.append("right")
        if height is not None:
            if y < ct: sides.append("top")
            if y + h > height - cb: sides.append("bottom")
        if x + w <= lo or x >= hi: sides = ["outside"]
        if sides: bad.append((i, x, y, w, h, "+".join(sides)))
    return bad


def run(path, width, cl, cr, height, ct, cb, max_report):
    n = nobj = nfixed = nbad = 0; shown = 0; rows = []; worst = 0
    with open(path) as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line: continue
            try: fr = json.loads(line); objs = fr["objs"]
            except (ValueError, KeyError): print("bad line %d" % ln, file=sys.stderr); return None
            n += 1; nobj += len(objs); nfixed += sum(1 for o in objs if o[4]); bad = check_frame(objs, width, cl, cr, height, ct, cb)
            nbad += len(bad)
            for b in bad:
                cut = max(cl - b[1], b[1] + b[3] - (width - cr), 0); worst = max(worst, cut)
                if shown < max_report: print("frame %s%s: fixed object %d at x=%d y=%d w=%d h=%d is cut (%s)" % (fr.get("frame", ln), (" mode %s" % fr["mode"]) if "mode" in fr else "", b[0], b[1], b[2], b[3], b[4], b[5])); shown += 1
                rows.append(dict(frame=fr.get("frame", ln), obj=b[0], x=b[1], y=b[2], w=b[3], h=b[4], side=b[5]))
    return dict(frames=n, objects=nobj, fixed=nfixed, clipped=nbad, worst_px=worst, rows=rows[:1000])


def selftest():
    ok = True
    def t(name, cond):
        nonlocal ok
        print(("ok   " if cond else "FAIL ") + name); ok = ok and cond
    t("fixed object whole is fine", check_frame([[16, 0, 32, 16, 1]], 384, 16, 16) == [])
    t("fixed object on the left edge is cut", len(check_frame([[0, 0, 32, 16, 1]], 384, 16, 16)) == 1)
    t("fixed object on the right edge is cut", len(check_frame([[360, 0, 24, 16, 1]], 384, 16, 16)) == 1)
    t("world object in the strip is not checked", check_frame([[0, 0, 32, 16, 0]], 384, 16, 16) == [])
    t("fixed object wholly in the strip is reported outside", check_frame([[0, 0, 16, 16, 1]], 384, 16, 16)[0][5] == "outside")
    t("flush with the window edge is whole", check_frame([[16, 0, 352, 8, 1]], 384, 16, 16) == [] and check_frame([[17, 0, 352, 8, 1]], 384, 16, 16)[0][5] == "right")
    t("vertical crop", len(check_frame([[100, 0, 8, 8, 1]], 384, 0, 0, 224, 8, 8)) == 1)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("frames", nargs="?"); ap.add_argument("--width", type=int); ap.add_argument("--crop", type=int, default=0, help="pixels cropped off the left side (and the right side unless --crop-right)")
    ap.add_argument("--crop-right", type=int, default=None); ap.add_argument("--height", type=int); ap.add_argument("--crop-top", type=int, default=0); ap.add_argument("--crop-bottom", type=int, default=0)
    ap.add_argument("--max-report", type=int, default=20); ap.add_argument("--json", help="write the summary here"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    if not a.frames or not a.width: ap.error("FRAMES.jsonl and --width are required")
    cr = a.crop if a.crop_right is None else a.crop_right
    r = run(a.frames, a.width, a.crop, cr, a.height, a.crop_top, a.crop_bottom, a.max_report)
    if r is None: return 2
    print("%d frames, %d objects, %d screen-fixed, %d clipped by the crop (worst cut %d px)" % (r["frames"], r["objects"], r["fixed"], r["clipped"], r["worst_px"]))
    if a.json: json.dump(r, open(a.json, "w"), indent=1)
    return 1 if r["clipped"] else 0


if __name__ == "__main__":
    sys.exit(main())
