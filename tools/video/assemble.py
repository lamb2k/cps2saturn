#!/usr/bin/env python3
"""Assemble captured frame folders into a looping 1080p video from an edit list (EDL, JSON).

Game-neutral. It reads PNG frame folders (for example from tools/clip/shot_script.py), composes every output
picture in Python and encodes with ffmpeg. No editor, no window. Nothing here uploads anything.

Third-party packages are optional at import time and needed at run time:
  Pillow (pictures), imageio-ffmpeg (a bundled ffmpeg; a system ffmpeg on PATH works too).

usage:
  assemble.py EDL.json                 full render: master mp4, the export presets, poster, contact sheet, report
  assemble.py EDL.json --draft         half size, fast encode, for checking the cut
  assemble.py EDL.json --sheet         contact sheet and report only (no video)
  assemble.py --probe FRAME_DIR        print the picture box (crop) of a capture folder, for the EDL's "crop"
  assemble.py --smooth FRAME_DIR       distinct pictures per 60 in a capture (60 = the game drew a new picture every frame)

EDL keys
  title, out            output name stem and folder
  fps (60), size ([1920, 1080]), frames (1800 = 30 s at 60)
  font                  a .ttf path. Without it a font is searched for (see find_font), then Pillow's default.
  tag_font              the same for the small corner tags (default: the main font)
  crop                  [x, y, w, h] of the game picture inside a captured frame, or "auto" (per clip, slower,
                        can be fooled by dark scenes)
  display_aspect        [4, 3]: the picture is shown at the TV's aspect whatever the capture's pixel shape
  loop_bridge           N: the last N frames dissolve into frame 0 so the loop has no jump (0 = none)
  tags                  [{text, at, dur, pos: "br"|"bl"|"tr"|"tl", size}] small corner labels (for example "Emulator capture")
  captions              [{text, at, dur, pos or y, size, color}] lines on the whole timeline (at is a video frame),
                        drawn over every clip
  shots_root            folder that relative clip "src" paths start from
  standin               a frame folder used for any clip whose own folder does not exist yet (listed under problems),
                        so a draft cut works early
  exports               names of export presets to write besides the master (default: web60, web30, silent60)
  export_presets        extra or replacement presets as {name: {...}} (same keys as EXPORT_PRESETS below)
  poster_frame          timeline frame for the poster still (default: the middle)
  audio_mix             a finished track from mix.py, laid at frame 0
  audio                 [{file, at (frame), in_s, dur_s, gain_db, fade_in_s, fade_out_s,
                          cdda: true for a raw 44.1 kHz stereo 16 bit track (.bin/.raw)}]
  clips                 drawn in list order, later ones on top:
    {id, at, dur, src, in (0), speed (1.0), hold: true (hold the last frame) or loop: true,
     layout: "pillar" (4:3 picture, blurred copy of itself in the side panels)
             | "fill" (cover 16:9, crops top and bottom; anchor_y 0..1)
             | "punch" (zoomed region: punch {from: [cx, cy, zoom], to: [cx, cy, zoom]}, cx cy 0..1 on the picture,
               zoom 1 = full width, zoom under 1 shows black around the picture),
     pixel: true (nearest-neighbour enlargement, for native-size frames),
     fade_in, fade_out (frames, to black), flash_in (frames of white flash at the cut), dim (0..1 darkening),
     captions: [{text, at, dur, pos: "bottom"|"top"|"center" or y (0..1, top of the text), size, color, stroke}]}
     (a clip caption's "at" is relative to the clip)
    {id, at, dur, card: {bg: "#000000" or an image path, lines: [{text, y (0..1), size, color}]},
     fade_in, fade_out, captions}

Export presets are named dicts, not site names: fps, video bitrate, max rate, buffer, GOP length, audio on or off.
Check each platform's own current limits before you upload. This tool never does.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    HAVE_PIL = True
except ImportError:  # optional: only needed to render
    Image = ImageDraw = ImageFilter = ImageFont = None  # type: ignore
    HAVE_PIL = False

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:  # optional: a system ffmpeg works too
    FFMPEG = "ffmpeg"

# Generic export presets. "fps" None = the timeline's own rate.
EXPORT_PRESETS: dict[str, dict] = {
    "web60": dict(suffix="1080p60_web", fps=None, bitrate="10M", maxrate="12M", bufsize="20M", gop=60, audio=True),
    "web30": dict(suffix="1080p30_web", fps=30, bitrate="8M", maxrate="10M", bufsize="16M", gop=30, audio=True),
    "silent60": dict(suffix="1080p60_silent", fps=None, bitrate="10M", maxrate="12M", bufsize="20M", gop=60, audio=False),
}
DEFAULT_EXPORTS = ["web60", "web30", "silent60"]

FONT_NAMES = ["impact.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "Helvetica.ttc"]


def require_pillow() -> None:
    if not HAVE_PIL:
        raise SystemExit("assemble.py needs Pillow: pip install Pillow")


def font_dirs() -> list[pathlib.Path]:
    dirs = []
    win = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if win:
        dirs.append(pathlib.Path(win) / "Fonts")
    dirs += [pathlib.Path(p) for p in ("/usr/share/fonts", "/usr/local/share/fonts", "/Library/Fonts", "/System/Library/Fonts")]
    dirs += [pathlib.Path.home() / ".fonts", pathlib.Path.home() / ".local/share/fonts"]
    return [d for d in dirs if d.is_dir()]


def find_font(preferred: str | None = None) -> str | None:
    """A font file: the EDL's own path, then $VIDEO_FONT, then a search of the system font folders. None = no file found."""
    for cand in (preferred, os.environ.get("VIDEO_FONT")):
        if cand and pathlib.Path(cand).is_file():
            return str(cand)
    for d in font_dirs():
        for name in FONT_NAMES:
            for hit in d.rglob(name):
                return str(hit)
    return None


_fonts: dict = {}


def font(path: str | None, size: int):
    """TrueType font at a pixel size; Pillow's built-in font when no file is found."""
    size = max(8, int(size))
    key = (path, size)
    if key not in _fonts:
        found = find_font(path)
        try:
            _fonts[key] = ImageFont.truetype(found, size) if found else ImageFont.load_default(size)
        except (OSError, TypeError):
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def load_rgb(path):
    """A picture file as RGB, with the file closed again."""
    with Image.open(path) as im:
        return im.convert("RGB")


def probe_box(folder, sample: int = 24, thr: int = 20):
    """Union of the non-black boxes of a sample of frames: [x, y, w, h], frame size, frame count."""
    require_pillow()
    fs = sorted(pathlib.Path(folder).glob("*.png"))
    if not fs:
        raise SystemExit("no png in " + str(folder))
    box = None
    for f in fs[::max(1, len(fs) // sample)]:
        with Image.open(f) as raw:
            b = raw.convert("L").point(lambda v: 255 if v > thr else 0).getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    if box is None:
        raise SystemExit("all sampled frames are black in " + str(folder))
    with Image.open(fs[0]) as first:
        size = first.size
    return [box[0], box[1], box[2] - box[0], box[3] - box[1]], size, len(fs)


def smoothness(folder) -> dict:
    """How many pictures differ from the one before, per 60: the game's real picture rate in a take."""
    fs = sorted(pathlib.Path(folder).glob("*.png"))
    box = probe_box(folder)[0]
    hs = [hashlib.md5(load_rgb(f).crop((box[0], box[1], box[0] + box[2], box[1] + box[3])).tobytes()).hexdigest() for f in fs]
    ch = [i for i in range(1, len(hs)) if hs[i] != hs[i - 1]]
    return dict(frames=len(hs), distinct_per_60=round(60 * len(ch) / max(1, len(hs) - 1), 1),
                per_second=[sum(1 for i in ch if a <= i < a + 60) for a in range(0, len(hs), 60)])


class Clip:
    def __init__(self, c: dict, edl: dict) -> None:
        self.c, self.edl = c, edl
        self.at, self.dur = int(c["at"]), int(c["dur"])
        self.files = None
        self.cache: tuple = (None, None)
        self.caps: dict = {}
        self.card_img = None
        self.standin = False
        if "src" in c:
            src = pathlib.Path(c["src"])
            if not src.is_absolute() and edl.get("shots_root"):
                src = pathlib.Path(edl["shots_root"]) / src
            self.files = sorted(src.glob("*.png"))
            if not self.files and edl.get("standin"):
                src = pathlib.Path(edl["standin"])
                self.files = sorted(src.glob("*.png"))
                self.standin = True
                c["loop"] = True
            if not self.files:
                raise SystemExit(f"clip {c['id']}: no frames in {src}")
            crop = c.get("crop", edl.get("crop", "auto"))
            self.crop = probe_box(src)[0] if crop == "auto" else crop

    def covers(self, t: int) -> bool:
        return self.at <= t < self.at + self.dur

    def src_frame(self, t: int):
        i = int(self.c.get("in", 0)) + int((t - self.at) * float(self.c.get("speed", 1.0)))
        n = len(self.files)
        if self.c.get("loop"):
            i %= n
        elif i >= n:
            if not self.c.get("hold", True):
                raise SystemExit(f"clip {self.c['id']}: needs frame {i}, folder has {n}")
            i = n - 1
        if self.cache[0] != i:
            x, y, w, h = self.crop
            self.cache = (i, load_rgb(self.files[i]).crop((x, y, x + w, y + h)))
        return self.cache[1]

    def picture(self, t: int, W: int, H: int):
        c = self.c
        if "card" in c:
            return self.card(W, H)
        src = self.src_frame(t)
        rs = Image.NEAREST if c.get("pixel") else Image.LANCZOS
        da = self.edl.get("display_aspect", [4, 3])
        dar = da[0] / da[1]
        layout = c.get("layout", "pillar")
        if layout == "pillar":
            pw = min(W, int(round(H * dar / 2)) * 2)
            ph = H
            bg = src.resize((96, 54), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BICUBIC).point(lambda v: int(v * 0.32))
            bg.paste(src.resize((pw, ph), rs), ((W - pw) // 2, 0))
            return bg
        # "fill" and "punch" both show a 16:9 window of the picture; the picture is first thought of as dar wide
        if layout == "fill":
            cx, cy, z = 0.5, None, 1.0
        else:
            p = c["punch"]
            u = (t - self.at) / max(1, self.dur - 1)
            u = u * u * (3 - 2 * u)  # smooth
            cx, cy, z = (p["from"][k] + (p["to"][k] - p["from"][k]) * u for k in range(3))
        sw, sh = src.size
        vw = sw / z                                # window width in source pixels
        vh = vw * (sh / sw) * dar * (H / W)        # window height so that it shows as 16:9 at the display aspect
        if cy is None:
            cy = 0.5 * vh / sh + float(c.get("anchor_y", 0.5)) * (1 - vh / sh)
        x0 = cx * sw - vw / 2
        y0 = cy * sh - vh / 2
        if vw <= sw:
            x0 = min(max(x0, 0), sw - vw)
        if vh <= sh:
            y0 = min(max(y0, 0), sh - vh)
        if vw <= sw and vh <= sh:
            return src.resize((W, H), rs, box=(x0, y0, x0 + vw, y0 + vh))
        return src.transform((W, H), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.NEAREST if c.get("pixel") else Image.BICUBIC, fillcolor="#000000")

    def card(self, W: int, H: int):
        if self.card_img is None or self.card_img.size != (W, H):
            k = self.c["card"]
            bg = k.get("bg", "#000000")
            if bg.startswith("#"):
                im = Image.new("RGB", (W, H), bg)
            else:
                art = load_rgb(bg)
                s = min(W / art.width, H / art.height) * float(k.get("bg_scale", 1.0))
                art = art.resize((int(art.width * s), int(art.height * s)), Image.NEAREST if k.get("pixel") else Image.LANCZOS)
                im = Image.new("RGB", (W, H), k.get("bg_fill", "#000000"))
                im.paste(art, ((W - art.width) // 2, int((H - art.height) * float(k.get("bg_y", 0.5)))))
                if k.get("bg_dim"):
                    im = im.point(lambda v: int(v * (1 - float(k["bg_dim"]))))
            d = ImageDraw.Draw(im)
            for ln in k.get("lines", []):
                f = font(self.edl.get("font"), int(ln.get("size", 96) * H / 1080))
                w = d.textlength(ln["text"], font=f)
                d.text(((W - w) / 2, ln.get("y", 0.5) * H), ln["text"], font=f, fill=ln.get("color", "#ffffff"),
                       stroke_width=int(ln.get("stroke", 6) * H / 1080), stroke_fill="#000000")
            self.card_img = im
        return self.card_img

    def alpha(self, t: int) -> float:
        c = self.c
        r = t - self.at
        a = 1.0
        if c.get("fade_in") and r < c["fade_in"]:
            a = min(a, (r + 1) / (c["fade_in"] + 1))
        if c.get("fade_out") and r >= self.dur - c["fade_out"]:
            a = min(a, (self.dur - r) / (c["fade_out"] + 1))
        return a

    def render(self, t: int, W: int, H: int):
        c = self.c
        r = t - self.at
        im = self.picture(t, W, H)
        if c.get("dim"):
            im = im.point(lambda v: int(v * (1 - float(c["dim"]))))
        if c.get("flash_in") and r < c["flash_in"]:
            im = Image.blend(im, Image.new("RGB", (W, H), "#ffffff"), 0.9 * (1 - r / c["flash_in"]))
        for j, cap in enumerate(c.get("captions", [])):
            cr = r - int(cap.get("at", 0))
            cd = int(cap.get("dur", self.dur))
            if 0 <= cr < cd:
                im = caption(self.caps, self.edl, j, cap, im, min(1.0, (cr + 1) / 6, (cd - cr) / 6), W, H)
        return im


def caption(cache: dict, edl: dict, j: int, cap: dict, im, a: float, W: int, H: int):
    """Draw one caption. `cache` holds the rendered text layer per (index, width)."""
    if (j, W) not in cache:
        f = font(edl.get("font"), int(cap.get("size", 84) * H / 1080))
        sw = int(cap.get("stroke", 7) * H / 1080)
        lines = cap["text"].split("\n")
        d = ImageDraw.Draw(im)
        ws = [d.textlength(ln, font=f) for ln in lines]
        lh = int(getattr(f, "size", 40) * 1.12)
        layer = Image.new("RGBA", (int(max(ws)) + 4 * sw, lh * len(lines) + 4 * sw), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for i, ln in enumerate(lines):
            ld.text(((layer.width - ws[i]) / 2, 2 * sw + i * lh), ln, font=f, fill=cap.get("color", "#ffffff"),
                    stroke_width=sw, stroke_fill=cap.get("stroke_color", "#000000"))
        if "y" in cap:
            y = int(cap["y"] * H) - 2 * sw
        else:
            y = {"top": int(0.06 * H), "center": (H - layer.height) // 2, "bottom": int(0.94 * H) - layer.height}[cap.get("pos", "bottom")]
        cache[(j, W)] = (layer, ((W - layer.width) // 2, y))
    layer, pos = cache[(j, W)]
    if a < 1.0:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    im = im.copy()
    im.paste(layer, pos, layer)
    return im


def compose(clips: list, edl: dict, t: int, W: int, H: int, gcache: dict | None = None):
    """One output picture at timeline frame t."""
    gcache = gcache if gcache is not None else edl.setdefault("_caption_cache", {})
    out = Image.new("RGB", (W, H), "#000000")
    for cl in clips:
        if cl.covers(t):
            a = cl.alpha(t)
            im = cl.render(t, W, H)
            out = im if a >= 1.0 else Image.blend(out, im, a)
    for j, cap in enumerate(edl.get("captions", [])):
        cr = t - int(cap.get("at", 0))
        cd = int(cap.get("dur", 10 ** 9))
        if 0 <= cr < cd:
            out = caption(gcache, edl, j, cap, out, min(1.0, (cr + 1) / 6, (cd - cr) / 6), W, H)
    for tg in edl.get("tags", []):
        if tg.get("at", 0) <= t < tg.get("at", 0) + tg.get("dur", 10 ** 9):
            f = font(edl.get("tag_font", edl.get("font")), int(tg.get("size", 26) * H / 1080))
            d = ImageDraw.Draw(out)
            w = d.textlength(tg["text"], font=f)
            m = int(0.022 * H)
            pos = tg.get("pos", "br")
            fs = getattr(f, "size", 26)
            xy = (W - w - m if "r" in pos else m, H - fs - m if "b" in pos else m)
            d.text(xy, tg["text"], font=f, fill=tg.get("color", "#d8d8d8"), stroke_width=max(1, int(2 * H / 1080)), stroke_fill="#000000")
    return out


def audio_args(edl: dict, fps: int, secs: float):
    """ffmpeg inputs and a filter graph that mixes every audio item at its frame, trimmed to the video length."""
    ins: list[str] = []
    fl: list[str] = []
    items = [dict(file=edl["audio_mix"], at=0)] if edl.get("audio_mix") else edl.get("audio", [])
    for i, a in enumerate(items):
        if a.get("cdda"):
            ins += ["-f", "s16le", "-ar", "44100", "-ac", "2"]
        if a.get("in_s"):
            ins += ["-ss", str(a["in_s"])]
        if a.get("dur_s"):
            ins += ["-t", str(a["dur_s"])]
        ins += ["-i", a["file"]]
        ch = [f"[{i + 1}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo", f"volume={a.get('gain_db', 0)}dB"]
        if a.get("fade_in_s"):
            ch.append(f"afade=t=in:st=0:d={a['fade_in_s']}")
        if a.get("fade_out_s") and a.get("dur_s"):
            ch.append(f"afade=t=out:st={a['dur_s'] - a['fade_out_s']}:d={a['fade_out_s']}")
        ms = int(round(1000 * a.get("at", 0) / fps))
        ch.append(f"adelay={ms}|{ms}")
        fl.append(",".join(ch) + f"[a{i}]")
    if not items:
        return [], None
    lim = "" if edl.get("audio_mix") else ",alimiter=limit=0.89"  # a mix.py track is already normalised to its true-peak target
    fl.append("".join(f"[a{i}]" for i in range(len(items))) + f"amix=inputs={len(items)}:normalize=0:duration=longest{lim},apad,atrim=0:{secs}[aout]")
    return ins, ";".join(fl)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise SystemExit("ffmpeg not found: pip install imageio-ffmpeg, or put ffmpeg on PATH")
    if r.returncode:
        raise SystemExit("ffmpeg failed:\n" + r.stderr.decode(errors="replace")[-1500:])
    return r


def x264_args(gop: int) -> list[str]:
    return ["-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709", "-g", str(gop), "-bf", "2"]


def resolve_exports(edl: dict) -> dict[str, dict]:
    presets = {**EXPORT_PRESETS, **edl.get("export_presets", {})}
    names = edl.get("exports", DEFAULT_EXPORTS)
    missing = [n for n in names if n not in presets]
    if missing:
        raise SystemExit("unknown export preset: " + ", ".join(missing) + " (known: " + ", ".join(sorted(presets)) + ")")
    return {n: presets[n] for n in names}


def contact_sheet(clips: list, edl: dict, N: int, fps: int, W: int, H: int, path: pathlib.Path) -> None:
    th = (384, 216)
    cols = 3
    sheet = Image.new("RGB", (cols * th[0], max(1, len(clips)) * (th[1] + 26)), "#101010")
    d = ImageDraw.Draw(sheet)
    lab = font(edl.get("font"), 16)
    for r, cl in enumerate(clips):
        for k, t in enumerate((cl.at, cl.at + cl.dur // 2, min(N, cl.at + cl.dur) - 1)):
            sheet.paste(compose(clips, edl, max(0, t), W, H).resize(th, Image.BILINEAR), (k * th[0], r * (th[1] + 26) + 26))
        d.text((6, r * (th[1] + 26) + 4), f"{cl.c['id']}   {cl.at / fps:.2f}s to {(cl.at + cl.dur) / fps:.2f}s", font=lab, fill="#ffd040")
    sheet.save(path)


def render(edl: dict, draft: bool = False, sheet_only: bool = False) -> dict:
    require_pillow()
    fps = int(edl.get("fps", 60))
    W, H = edl.get("size", [1920, 1080])
    N = int(edl.get("frames", 1800))
    if draft:
        W, H = W // 2, H // 2
    out = pathlib.Path(edl["out"])
    out.mkdir(parents=True, exist_ok=True)
    stem = edl.get("title", "video") + ("_draft" if draft else "")
    exports = resolve_exports(edl)
    clips = [Clip(c, edl) for c in edl["clips"]]
    report: dict = dict(title=edl.get("title"), fps=fps, size=[W, H], frames=N, seconds=N / fps, clips=[], problems=[])
    cover = [0] * N
    for cl in clips:
        for t in range(max(0, cl.at), min(N, cl.at + cl.dur)):
            cover[t] += 1
        need = None
        if cl.standin:
            report["problems"].append(f"clip {cl.c['id']}: its folder is missing, stand-in frames used")
        if cl.files is not None:
            need = int(cl.c.get("in", 0)) + int((cl.dur - 1) * float(cl.c.get("speed", 1.0))) + 1
            if need > len(cl.files) and not cl.c.get("loop"):
                report["problems"].append(f"clip {cl.c['id']}: wants {need} source frames, has {len(cl.files)} (last frame held)")
        report["clips"].append(dict(id=cl.c["id"], at=cl.at, dur=cl.dur, at_s=round(cl.at / fps, 2),
                                    source_frames=len(cl.files) if cl.files else None, needs=need))
    gaps = [t for t in range(N) if not cover[t]]
    if gaps:
        report["problems"].append(f"{len(gaps)} frames have no clip (black), first at {gaps[0]}")

    contact_sheet(clips, edl, N, fps, W, H, out / f"{stem}_sheet.png")
    report_path = out / f"{stem}_report.json"
    if sheet_only:
        report_path.write_text(json.dumps(report, indent=1))
        return report

    bridge = int(edl.get("loop_bridge", 0))
    first = compose(clips, edl, 0, W, H)
    video = out / f"{stem}_video_only.mp4"
    enc = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264", "-preset", "veryfast" if draft else "slow",
           "-crf", "24" if draft else "14", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
           "-color_trc", "bt709", "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709", "-an", str(video)]
    try:
        p = subprocess.Popen(enc, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise SystemExit("ffmpeg not found: pip install imageio-ffmpeg, or put ffmpeg on PATH")
    last = first
    for t in range(N):
        im = compose(clips, edl, t, W, H)
        if bridge and t >= N - bridge:
            im = Image.blend(im, first, (t - (N - bridge) + 1) / (bridge + 1))
        p.stdin.write(im.tobytes())
        last = im
        if t % 300 == 0:
            print(f"frame {t}/{N}", flush=True)
    p.stdin.close()
    err = p.stderr.read()
    p.stderr.close()
    if p.wait():
        raise SystemExit("ffmpeg failed:\n" + err.decode(errors="replace")[-1500:])
    first.save(out / f"{stem}_first.png")
    last.save(out / f"{stem}_last.png")
    a = first.resize((320, 180)).convert("L").tobytes()
    b = last.resize((320, 180)).convert("L").tobytes()
    # 0 = identical; under about 12 reads as one continuous dissolve
    report["loop_seam_mean_abs_diff"] = round(sum(abs(x - y) for x, y in zip(a, b)) / len(a), 2)
    compose(clips, edl, int(edl.get("poster_frame", N // 2)), W, H).save(out / f"{stem}_poster.png")

    ains, graph = audio_args(edl, fps, N / fps)
    common = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart"]
    amap = (["-filter_complex", graph, "-map", "0:v", "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
            if graph else ["-map", "0:v", "-an"])
    outs: dict[str, pathlib.Path] = {}
    outs["master"] = out / f"{stem}_1080p{fps}_master.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-i", str(video)] + ains + amap + ["-c:v", "copy"] + common + [str(outs["master"])])
    if not draft:
        for name, ps in exports.items():
            dest = out / f"{stem}_{ps['suffix']}.mp4"
            rate = ["-r", str(ps["fps"])] if ps.get("fps") and ps["fps"] != fps else []
            audio = amap if ps.get("audio", True) else ["-map", "0:v", "-an"]
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(video)] + (ains if ps.get("audio", True) else []) + audio + rate \
                + x264_args(int(ps.get("gop", fps))) + ["-b:v", ps["bitrate"], "-maxrate", ps["maxrate"], "-bufsize", ps["bufsize"]] + common + [str(dest)]
            run(cmd)
            outs[name] = dest
    os.remove(video)
    report["outputs"] = {k: dict(path=str(v), mb=round(v.stat().st_size / 1e6, 2)) for k, v in outs.items()}
    report_path.write_text(json.dumps(report, indent=1))
    return report


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) >= 2 and a[0] == "--smooth":
        require_pillow()
        print(json.dumps(smoothness(a[1])))
        return 0
    if len(a) >= 2 and a[0] == "--probe":
        box, size, n = probe_box(a[1])
        print(json.dumps(dict(frames=n, frame_size=size, crop=box, picture_aspect=round(box[2] / box[3], 4))))
        return 0
    if not a or a[0].startswith("-"):
        print(__doc__)
        return 2
    edl = json.loads(pathlib.Path(a[0]).read_text(encoding="utf-8"))
    flags = set(a[1:])
    rep = render(edl, draft="--draft" in flags, sheet_only="--sheet" in flags)
    print(json.dumps(dict(problems=rep["problems"], loop_seam=rep.get("loop_seam_mean_abs_diff"), outputs=rep.get("outputs")), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
