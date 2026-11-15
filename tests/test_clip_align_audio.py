import json
import pathlib
import tempfile
import unittest

import _util  # noqa: F401

_util.sys.path.insert(0, str(_util.TOOLS / "clip"))
try:
    import numpy as np
    import align_audio
    HAVE = True
except ImportError:
    HAVE = False

RATE = 22050
VB_PER_S = 60.0
V0, FRAMES = 100, 120
LATENCY = 0.12          # the synthetic audio pipeline's delay
T0 = 1.0                # wall time of the recording's first sample
EVENT_VBLANKS = (130, 170)


def synth():
    """Polls every 5 ms with two state changes, and a recording with a tone burst LATENCY after each."""
    polls = []
    t = T0
    while t < 5.0:
        v = int(t * VB_PER_S)
        state = "00"
        if 130 <= v < 140:
            state = "0a"
        elif 170 <= v < 180:
            state = "0b"
        polls.append([round(t, 4), v, state])
        t += 0.005
    n = int((5.0 - T0) * RATE)
    rng = np.random.default_rng(3)
    pcm = (rng.standard_normal((n, 2)) * 0.001).astype(np.float32)
    for ev in EVENT_VBLANKS:
        s = int((ev / VB_PER_S + LATENCY - T0) * RATE)
        k = np.arange(int(0.1 * RATE))
        tone = (0.5 * np.sin(2 * np.pi * 1000 * k / RATE)).astype(np.float32)
        pcm[s:s + len(k), 0] += tone
        pcm[s:s + len(k), 1] += tone
    return polls, pcm


@unittest.skipUnless(HAVE, "numpy not installed")
class AlignAudioTest(unittest.TestCase):
    def test_latency_and_cut(self):
        polls, pcm = synth()
        seg, rep = align_audio.align(pcm, RATE, T0, polls, V0, FRAMES, {"00"})
        self.assertAlmostEqual(rep["clock"]["vblank_per_s"], VB_PER_S, delta=0.5)
        self.assertEqual(len(rep["events"]), 2)
        self.assertAlmostEqual(rep["latency_s"], LATENCY, delta=0.02)
        self.assertLess(rep["alignment_error_ms"]["max_abs"], 20)
        self.assertEqual(len(seg), int((FRAMES / 60 + 1.0) * RATE))
        # the first event is 30 pictures after picture 0, so its tone starts 0.5 s into the cut
        loud = int(np.argmax(np.abs(seg[:, 0]) > 0.2))
        self.assertAlmostEqual(loud / RATE, (EVENT_VBLANKS[0] - V0) / VB_PER_S, delta=0.02)

    def test_given_latency_is_used(self):
        polls, pcm = synth()
        _seg, rep = align_audio.align(pcm, RATE, T0, polls, V0, FRAMES, {"00"}, latency=0.1)
        self.assertEqual(rep["latency_source"], "given")
        self.assertEqual(rep["latency_s"], 0.1)

    def test_key_events_when_no_state_changes(self):
        polls, _pcm = synth()
        flat = [[t, v, "00"] for t, v, _s in polls]
        trace = [{"f": 30, "n": 10, "keys": ["a"]}, {"f": 40, "n": 10, "keys": []}, {"f": 70, "n": 10, "keys": ["b"]}]
        ev = align_audio.find_events(flat, V0, FRAMES, {"00"}, trace)
        self.assertEqual(ev, [(130, "key:a"), (170, "key:b")])

    def test_command_line(self):
        polls, pcm = synth()
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            (d / "polls.json").write_text(json.dumps(dict(V0=V0, frames=FRAMES, polls=polls)))
            align_audio.write_wav(d / "game.wav", pcm, RATE)
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                rc = align_audio.main(["--polls", str(d / "polls.json"), "--wav", str(d / "game.wav"), "--wav-t0", str(T0),
                                       "--idle-states", "00", "--out", str(d / "aligned.wav")])
            self.assertEqual(rc, 0)
            self.assertTrue((d / "aligned.wav").exists())
            self.assertIn("clock", json.loads((d / "aligned.json").read_text()))
            seg, rate = align_audio.read_wav(d / "aligned.wav")
            self.assertEqual(rate, RATE)
            self.assertEqual(seg.shape[1], 2)


if __name__ == "__main__":
    unittest.main()
