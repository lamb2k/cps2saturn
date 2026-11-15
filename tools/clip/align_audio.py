#!/usr/bin/env python3
"""Cut a real-time audio recording so that sample 0 is the start of picture 0 of a stepped take.

Game-neutral. A stepped take (tools/clip/shot_script.py) is silent and has no wall clock: its pictures are numbered by
the game's own vblank counter. To lay game sound under it, replay the same take in real time with sound on, record the
emulator's audio, and poll (wall time, vblank, player state) at the same moment. This tool then
  1. fits a line of vblank against wall time over the take (slope = emulated vblanks per second; residual = jitter),
  2. finds game events (the polled player state changes into a non-idle state; key presses when there are no state
     changes, as in menus) and the first sound onset after each,
  3. takes the median event-to-onset delay as the audio pipeline's latency (or uses --latency),
  4. cuts the recording from T(V0) + latency, one second longer than the take, and writes it as 16 bit stereo wav,
  5. reports the clock fit, per-event onsets and deviations (milliseconds) and the alignment error to quote.
The alignment is only as good as the spread of those deviations. Say so when you use the sound.

Third-party package, needed at run time: numpy.

usage: align_audio.py --polls POLLS.json --wav GAME.wav --wav-t0 SECONDS --take TAKE.json --out ALIGNED.wav
                      [--fps 60] [--idle-states 000000,000002] [--latency SECONDS]

Inputs
  --polls     JSON {"V0": first vblank of the take, "frames": pictures in the take,
                    "polls": [[wall_seconds, vblank, state_hex], ...]}  written by your own replay loop
  --wav       the recording, PCM 16 bit
  --wav-t0    wall-clock time (the same clock as the polls) of the recording's first sample
  --take      take.json from shot_script.py (key presses are the fallback events; its V0 is not needed here)
  --idle-states  comma list of state values that do not count as events (the idle/walk states)
  --fps       the video's picture rate (the cut is frames/fps seconds plus one second)
Writes ALIGNED.wav and ALIGNED.json (the report) beside it.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import wave

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:  # optional: only needed to align
    np = None  # type: ignore
    HAVE_NUMPY = False


def require_numpy() -> None:
    if not HAVE_NUMPY:
        raise SystemExit("align_audio.py needs numpy: pip install numpy")


def fit_clock(polls: list, v0: int, frames: int):
    """Line fit of the first wall time each vblank value was seen. Returns (slope s/vblank, offset s, report dict)."""
    first: dict[int, float] = {}
    for t, v, _s in polls:
        if v not in first:
            first[v] = t
    vs = np.array(sorted(x for x in first if v0 - 5 <= x <= v0 + frames + 30), dtype=float)
    if len(vs) < 2:
        raise SystemExit("not enough polls inside the take to fit a clock")
    ts = np.array([first[int(v)] for v in vs])
    a_mat = np.vstack([vs, np.ones_like(vs)]).T
    (a, b), *_ = np.linalg.lstsq(a_mat, ts, rcond=None)
    res = ts - (a * vs + b)
    return float(a), float(b), dict(vblank_per_s=round(1 / float(a), 3), residual_std_ms=round(float(res.std() * 1000), 2),
                                    residual_max_ms=round(float(abs(res).max() * 1000), 2))


def find_events(polls: list, v0: int, frames: int, idle_states: set, trace: list | None) -> list[tuple[int, str]]:
    """State changes into a non-idle state inside the take; key presses of the trace when fewer than two."""
    ev: list[tuple[int, str]] = []
    prev = None
    for _t, v, s in polls:
        if v < v0 or v > v0 + frames:
            prev = s
            continue
        if prev is not None and s != prev and s not in idle_states:
            ev.append((v, s))
        prev = s
    if len(ev) < 2 and trace:
        pk: list = []
        for tr in trace:
            if tr["keys"] and tr["keys"] != pk:
                ev.append((v0 + tr["f"], "key:" + "+".join(tr["keys"])))
            pk = tr["keys"]
        ev.sort()
    return ev


def envelope(mono, rate: int, hop_s: float = 0.005):
    """Energy envelope in 5 ms windows, high-passed by differencing so a steady hiss is ignored."""
    hop = max(1, int(rate * hop_s))
    env = np.sqrt(np.convolve(np.diff(mono, prepend=0) ** 2, np.ones(hop) / hop, "same"))[::hop]
    return env, hop


def onset_after(env, hop: int, floor: float, rate: int, t0: float, t_wall: float, win=(-0.05, 0.6)):
    """Wall time of the first window after the event whose envelope is clearly above what came just before it."""
    i0 = int((t_wall + win[0] - t0) * rate / hop)
    i1 = int((t_wall + win[1] - t0) * rate / hop)
    if i0 < 12 or i1 >= len(env):
        return None
    base = env[i0 - 12:i0].mean() + 3 * floor
    for i in range(i0, i1):
        if env[i] > 3.0 * base and env[i] > 8 * floor:
            return i * hop / rate + t0
    return None


def align(pcm, rate: int, t0: float, polls: list, v0: int, frames: int, idle_states: set, trace: list | None = None,
          fps: int = 60, latency: float | None = None):
    """Returns (aligned float32 (n, 2) segment, report dict). pcm is float32 (n, 2) in -1..1."""
    require_numpy()
    a, b, clock = fit_clock(polls, v0, frames)
    wall = lambda v: a * v + b      # wall time of vblank v  # noqa: E731
    ev = find_events(polls, v0, frames, idle_states, trace)
    mono = pcm.mean(axis=1)
    env, hop = envelope(mono, rate)
    floor = float(np.median(env)) + 1e-5
    offs, rows = [], []
    last_v = -99
    for v, s in ev:
        if v - last_v < 20:     # one onset per burst of state changes
            continue
        last_v = v
        tw = wall(v)
        on = onset_after(env, hop, floor, rate, t0, tw)
        if on is not None:
            offs.append(on - tw)
            rows.append(dict(vblank=v, picture=v - v0, state=s, onset_after_event_ms=round((on - tw) * 1000, 1)))
    if latency is not None:
        lat, src = latency, "given"
    elif offs:
        lat, src = float(np.median(offs)), "median of %d events" % len(offs)
    else:
        lat, src = 0.0, "none measured (0)"
    for r in rows:
        r["deviation_ms"] = round(r["onset_after_event_ms"] - lat * 1000, 1)
    dev = [abs(r["deviation_ms"]) for r in rows]
    # the sound of an event is heard `lat` seconds after the event's vblank, so picture 0 takes the recording from T(V0) + lat
    start = int(round((wall(v0) + lat - t0) * rate))
    length = int((frames / fps + 1.0) * rate)
    seg = np.zeros((length, 2), np.float32)
    lo, hi = max(0, start), min(len(pcm), start + length)
    if hi > lo:
        seg[lo - start:hi - start] = pcm[lo:hi]
    report = dict(clock=clock, latency_s=round(lat, 4), latency_source=src, events=rows,
                  alignment_error_ms=dict(max_abs=round(max(dev), 1) if dev else None,
                                          median_abs=round(float(np.median(dev)), 1) if dev else None, events=len(dev)),
                  audio=dict(peak=round(float(abs(seg).max()), 3), rms=round(float(np.sqrt((seg ** 2).mean())), 4),
                             seconds=round(length / rate, 2), recorded_seconds=round(len(pcm) / rate, 2)))
    return seg, report


def read_wav(path) -> tuple:
    """PCM 16 bit wav -> (float32 (n, 2), rate). Mono is doubled."""
    require_numpy()
    with wave.open(str(path)) as w:
        if w.getsampwidth() != 2:
            raise SystemExit("only 16 bit PCM wav is supported")
        n, ch, rate = w.getnframes(), w.getnchannels(), w.getframerate()
        pcm = np.frombuffer(w.readframes(n), "<i2").reshape(-1, ch).astype(np.float32) / 32768
    if ch == 1:
        pcm = np.repeat(pcm, 2, axis=1)
    return pcm[:, :2], rate


def write_wav(path, seg, rate: int) -> None:
    out = (np.clip(seg, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(out.tobytes())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--polls", required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--wav-t0", type=float, required=True)
    ap.add_argument("--take", help="take.json from shot_script.py (key-press fallback events)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--idle-states", default="")
    ap.add_argument("--latency", type=float)
    a = ap.parse_args(argv)
    pj = json.loads(pathlib.Path(a.polls).read_text())
    pcm, rate = read_wav(a.wav)
    trace = json.loads(pathlib.Path(a.take).read_text())["trace"] if a.take else None
    idle = {s.strip().lower() for s in a.idle_states.split(",") if s.strip()}
    seg, rep = align(pcm, rate, a.wav_t0, pj["polls"], int(pj["V0"]), int(pj["frames"]), idle, trace, a.fps, a.latency)
    write_wav(a.out, seg, rate)
    pathlib.Path(a.out).with_suffix(".json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
