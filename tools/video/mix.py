#!/usr/bin/env python3
"""Build the sound track of a captured video: game-sound cuts, a ducked music bed, voice lines, loudness target.

Game-neutral. Reads the same edit list (EDL, JSON) as assemble.py and writes <out>/<title>_mix.wav (48 kHz stereo
16 bit, exactly frames/fps seconds) after normalising it to the EDL's loudness target. Prints a JSON report, also
written to <out>/<title>_mix_report.json. Nothing here uploads anything.

Third-party packages are optional at import time and needed at run time: numpy, and ffmpeg
(imageio-ffmpeg bundles one; a system ffmpeg on PATH works too).

usage: mix.py EDL.json
       mix.py --measure FILE        EBU R128 integrated loudness and true peak of an audio file

Expected take layout (what tools/clip/ produces and what clips[].snd points at):
  <shots_root>/<take>/aligned.wav            or  <shots_root>/<take>/audio/aligned.wav
  The game's own sound for one take, any format ffmpeg reads, sample 0 = the start of the take's picture 0, running at
  the same picture rate as the stepped pictures (`fps` below). tools/clip/align_audio.py writes one from a
  real-time recording; an exact dump from a patched emulator can be laid out the same way.
  <shots_root>/<take>/f000000.png ...        the pictures that the clip's `src` reads (assemble.py)

Layers (all from the EDL):
  clips[].snd   {"take": "<clip>/<take>", "gain_db": 0}   the game's sound for that shot. The shot's `in`, `dur` and
                `speed` pick the part and stretch it (speed 0.5 = half-speed picture, sound resampled the same way,
                so its pitch drops). `xfade_ms` (default 60) cross-fades neighbouring cuts.
  music         the EDL audio item with "cdda": true (a raw 44.1 kHz stereo 16 bit track), with a gain envelope:
                "music": {"base_db", "duck_db", "ducks": [[t0_s, t1_s], ...], "duck_ramp_s", "loop_xfade_s"}
                (ducked under the action shots, up under the cards), 0.3 s ramps. When the track is long enough,
                the first loop_xfade_s seconds cross-fade with the music that follows the end, so a looping video
                has a seamless bed.
  voices        every other EDL audio item (a file laid at a frame): {file, at, gain_db, len_s, duck (default true),
                no_duck, skip_if_in_game}. "voice_duck_db" is the extra duck of the music under each voice, for len_s
                seconds (default 2.5). "skip_if_in_game": true leaves the voice out when the game recording already
                holds it (found by cross-correlation, reported).
  loudness      "loudness": {"i": -14, "tp": -1.5}: ffmpeg loudnorm, two passes, linear; the report holds the
                before and after figures. "comp": {threshold, ratio, attack, release, makeup} adds a gentle
                compressor first, to even the level.
Fades: 6 ms minimum on every game-sound cut; the music bed is cross-faded tail into head and nothing else plays
at the loop point.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import wave

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:  # optional: only needed to mix
    np = None  # type: ignore
    HAVE_NUMPY = False

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:  # optional: a system ffmpeg works too
    FFMPEG = "ffmpeg"
SR = 48000


def require_numpy() -> None:
    if not HAVE_NUMPY:
        raise SystemExit("mix.py needs numpy: pip install numpy")


def decode(path, cdda: bool = False):
    """Any audio file -> float32 (n, 2) at 48 kHz. cdda: a raw 44.1 kHz stereo 16 bit track."""
    require_numpy()
    cmd = [FFMPEG, "-v", "error"] + (["-f", "s16le", "-ar", "44100", "-ac", "2"] if cdda else []) + \
        ["-i", str(path), "-ar", str(SR), "-ac", "2", "-f", "f32le", "-"]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise SystemExit("ffmpeg not found: pip install imageio-ffmpeg, or put ffmpeg on PATH")
    if r.returncode:
        raise SystemExit("ffmpeg decode failed: %s\n%s" % (path, r.stderr.decode(errors="replace")[-400:]))
    return np.frombuffer(r.stdout, "<f4").reshape(-1, 2).copy()


def db(x: float) -> float:
    return 10 ** (x / 20)


def ramp_env(n: int, spans, base: float, low: float, ramp: float = 0.3):
    """Gain curve: `base` dB, `low` dB inside the spans (seconds), with ramps of `ramp` seconds."""
    t = np.arange(n) / SR
    g = np.full(n, float(base))
    for a, b in spans:
        up = np.clip((t - (a - ramp)) / ramp, 0, 1) * np.clip(((b + ramp) - t) / ramp, 0, 1)
        g = np.minimum(g, base + (low - base) * up) if low < base else np.maximum(g, base + (low - base) * up)
    return 10 ** (g / 20)


def place(buf, seg, at_s: float) -> None:
    a = int(round(at_s * SR))
    lo = max(0, a)
    hi = min(len(buf), a + len(seg))
    if hi > lo:
        buf[lo:hi] += seg[lo - a:hi - a]


def measure(path) -> dict:
    """EBU R128 integrated loudness and true peak of an audio file, via ffmpeg ebur128."""
    r = subprocess.run([FFMPEG, "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], stderr=subprocess.PIPE)
    t = r.stderr.decode(errors="replace")
    sm = t[t.rfind("Summary:"):]
    i = re.search(r"\bI: +(-?[\d.]+) LUFS", sm)
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", sm)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", sm)
    return dict(integrated_lufs=float(i[1]) if i else None, lra=float(lra[1]) if lra else None,
                true_peak_dbtp=float(tp[1]) if tp else None)


def loudnorm(src, dst, i: float, tp: float) -> dict:
    p1 = subprocess.run([FFMPEG, "-nostats", "-i", str(src), "-af", f"loudnorm=I={i}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                        stderr=subprocess.PIPE)
    t = p1.stderr.decode(errors="replace")
    j = json.loads(t[t.rfind("{"):t.rfind("}") + 1])
    flt = (f"loudnorm=I={i}:TP={tp}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
           f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true:print_format=summary,aresample={SR}")
    r = subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(src), "-af", flt, "-ar", str(SR), "-c:a", "pcm_s16le", str(dst)],
                       stderr=subprocess.PIPE)
    if r.returncode:
        raise SystemExit("loudnorm failed: " + r.stderr.decode(errors="replace")[-400:])
    return j


def xcorr_contains(rec, voice) -> float:
    """Normalised cross-correlation peak of a short voice file against a recording (FFT).
    About 0.5 and up means the recording holds it."""
    if len(voice) > len(rec) or len(voice) < SR // 10:
        return 0.0
    a = rec.mean(1)
    b = voice.mean(1)
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    c = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)[:len(a) - len(b) + 1]
    e = np.sqrt(np.convolve(a * a, np.ones(len(b)), "valid")) * np.sqrt((b * b).sum()) + 1e-9
    return float(np.max(c / e))


def write_wav(path, x) -> None:
    wv = wave.open(str(path), "wb")
    wv.setnchannels(2)
    wv.setsampwidth(2)
    wv.setframerate(SR)
    wv.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    wv.close()


def find_take_audio(shots: pathlib.Path, take: str) -> pathlib.Path:
    f = shots / take / "aligned.wav"
    return f if f.exists() else shots / take / "audio" / "aligned.wav"


def mix(edl: dict) -> dict:
    require_numpy()
    fps = int(edl.get("fps", 60))
    n_frames = int(edl.get("frames", 1800))
    out = pathlib.Path(edl["out"])
    out.mkdir(parents=True, exist_ok=True)
    shots = pathlib.Path(edl.get("shots_root", "."))
    secs = n_frames / fps
    length = int(round(secs * SR))
    game = np.zeros((length, 2), np.float32)
    report: dict = dict(game_clips=[], voices=[])
    xf = float(edl.get("xfade_ms", 60)) / 1000

    for c in edl["clips"]:
        s = c.get("snd")
        if not s:
            continue
        f = find_take_audio(shots, s["take"])
        if not f.exists():
            report["game_clips"].append(dict(id=c["id"], missing=f.name))
            continue
        w = decode(f)
        sp = float(c.get("speed", 1.0))
        a0 = int(c.get("in", 0)) / fps
        need = c["dur"] * sp / fps
        pre = min(xf / 2 * sp, a0)       # pre and post roll so neighbouring clips cross-fade instead of leaving a hole
        post = xf / 2 * sp
        seg = w[int((a0 - pre) * SR):int((a0 + need + post) * SR)]
        if len(seg) < 2:
            report["game_clips"].append(dict(id=c["id"], empty=True))
            continue
        want = int(round((c["dur"] / fps + (pre + post) / sp) * SR))
        x = np.linspace(0, len(seg) - 1, want)
        seg = np.stack([np.interp(x, np.arange(len(seg)), seg[:, k]) for k in (0, 1)], 1).astype(np.float32)
        fd = max(8, min(int(xf * SR), len(seg) // 2))
        seg[:fd] *= np.linspace(0, 1, fd)[:, None]
        seg[-fd:] *= np.linspace(1, 0, fd)[:, None]
        place(game, seg * db(float(s.get("gain_db", 0))), c["at"] / fps - pre / sp)
        report["game_clips"].append(dict(id=c["id"], at_s=round(c["at"] / fps, 2), seconds=round(c["dur"] / fps, 2),
                                         rms_db=round(float(20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)), 1)))

    mixbus = game.copy()
    mus = edl.get("music", {})
    ducks = mus.get("ducks", [])
    for a in edl.get("audio", []):
        if not a.get("cdda"):
            continue
        m = decode(a["file"], cdda=True)
        st = int(a.get("in_s", 0) * SR)
        xl = int(float(mus.get("loop_xfade_s", 1.2)) * SR)
        m = m[st:st + length + xl]                      # the video's length plus the head room for the loop cross-fade
        lm = np.zeros((length, 2), np.float32)
        lm[:min(length, len(m))] = m[:length]
        if len(m) >= length + xl and xl > 0:            # seamless loop: the music that follows the end, faded into the head
            w = np.linspace(0, 1, xl)[:, None].astype(np.float32)
            lm[:xl] = m[:xl] * w + m[length:length + xl] * (1 - w)
        lm *= ramp_env(length, ducks, mus.get("base_db", a.get("gain_db", -7)), mus.get("duck_db", -18), float(mus.get("duck_ramp_s", 0.3)))[:, None]
        vduck = [(v["at"] / fps, v["at"] / fps + v.get("len_s", 2.5)) for v in edl["audio"]
                 if not v.get("cdda") and v.get("duck", True) and not v.get("no_duck")]
        if vduck:
            lm *= ramp_env(length, vduck, 0, edl.get("voice_duck_db", -6), 0.15)[:, None]
        mixbus += lm

    for a in edl.get("audio", []):
        if a.get("cdda"):
            continue
        v = decode(a["file"])
        info = dict(file=pathlib.Path(a["file"]).name, at_s=round(a["at"] / fps, 2))
        if a.get("skip_if_in_game"):
            win = game[int(max(0, a["at"] / fps - 0.5) * SR):int(min(secs, a["at"] / fps + len(v) / SR + 1.0) * SR)]
            info["xcorr_in_game"] = round(xcorr_contains(win, v), 3)
            if info["xcorr_in_game"] >= 0.5:
                info["skipped"] = "the game recording already holds it"
                report["voices"].append(info)
                continue
        place(mixbus, v * db(float(a.get("gain_db", 0))), a["at"] / fps)
        report["voices"].append(info)

    title = edl.get("title", "video")
    pre_path = out / (title + "_mix_pre.wav")
    post_path = out / (title + "_mix.wav")
    pk = float(abs(mixbus).max())
    mixbus = mixbus / max(1.0, pk / 0.95)
    write_wav(pre_path, mixbus)
    tgt = edl.get("loudness", dict(i=-14, tp=-1.5))
    comp = edl.get("comp")
    if comp:   # gentle compression evens the level so quiet stretches stay within a few LU of the loud ones
        c2 = out / (title + "_mix_comp.wav")
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", str(pre_path), "-af",
                        "acompressor=threshold=%s:ratio=%s:attack=%s:release=%s:makeup=%s" % (
                            comp.get("threshold", 0.05), comp.get("ratio", 3), comp.get("attack", 15), comp.get("release", 300), comp.get("makeup", 2)),
                        "-c:a", "pcm_s16le", str(c2)], check=True)
        pre_path = c2
    report["before"] = measure(pre_path)
    loudnorm(pre_path, post_path, tgt["i"], tgt["tp"])
    report["after"] = measure(post_path)
    report["target"] = tgt
    report["seconds"] = secs
    (out / (title + "_mix_report.json")).write_text(json.dumps(report, indent=1))
    return report


def main(argv: list[str] | None = None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print(__doc__)
        return 2
    if a[0] == "--measure":
        print(json.dumps(measure(a[1])))
        return 0
    edl = json.loads(pathlib.Path(a[0]).read_text(encoding="utf-8"))
    print(json.dumps(mix(edl), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
