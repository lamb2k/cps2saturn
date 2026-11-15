import json
import pathlib
import tempfile
import unittest
import wave

import _util  # noqa: F401

_util.sys.path.insert(0, str(_util.TOOLS / "video"))
import mix  # noqa: E402  (imports without numpy)

try:
    import numpy as np
    HAVE = True
except ImportError:
    HAVE = False


def have_ffmpeg() -> bool:
    try:
        import subprocess
        subprocess.run([mix.FFMPEG, "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def sine_wav(path, hz, secs, rate=48000, amp=0.3):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(secs * rate)) / rate
    x = (np.sin(2 * np.pi * hz * t) * amp * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(np.repeat(x[:, None], 2, axis=1).tobytes())


class MixNoDepsTest(unittest.TestCase):
    def test_no_game_specific_wording(self):
        text = (_util.TOOLS / "video" / "mix.py").read_text(encoding="utf-8").lower()
        for bad in ("avp", "reveal", "scsp", "claw"):
            self.assertNotIn(bad, text)

    def test_usage_without_arguments(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mix.main([]), 2)


@unittest.skipUnless(HAVE, "numpy not installed")
class MixTest(unittest.TestCase):
    def test_ramp_envelope_ducks_inside_the_span(self):
        env = mix.ramp_env(mix.SR * 4, [(1.0, 2.0)], 0, -12)
        self.assertAlmostEqual(float(env[0]), 1.0, places=3)
        self.assertAlmostEqual(float(env[int(1.5 * mix.SR)]), 10 ** (-12 / 20), places=3)

    def test_xcorr_finds_a_contained_voice(self):
        rng = np.random.default_rng(2)
        voice = (rng.standard_normal((mix.SR // 2, 2)) * 0.3).astype(np.float32)
        rec = (rng.standard_normal((mix.SR * 2, 2)) * 0.01).astype(np.float32)
        rec[mix.SR // 4:mix.SR // 4 + len(voice)] += voice
        self.assertGreater(mix.xcorr_contains(rec, voice), 0.5)
        self.assertLess(mix.xcorr_contains(rec * 0 + 0.001 * rng.standard_normal(rec.shape).astype(np.float32), voice), 0.5)

    @unittest.skipUnless(have_ffmpeg(), "ffmpeg not available")
    def test_full_mix_with_game_music_and_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            sine_wav(tmp / "shots" / "clip1" / "t1" / "audio" / "aligned.wav", 440, 3.0)
            sine_wav(tmp / "voice.wav", 880, 0.6)
            # a raw 44.1 kHz stereo 16 bit "music" track, a little longer than the video
            t = np.arange(int(5.0 * 44100)) / 44100
            m = (np.sin(2 * np.pi * 220 * t) * 0.3 * 32767).astype("<i2")
            (tmp / "music.raw").write_bytes(np.repeat(m[:, None], 2, axis=1).tobytes())
            edl = dict(title="t", out=str(tmp / "out"), shots_root=str(tmp / "shots"), fps=30, frames=90,
                       clips=[dict(id="a", at=0, dur=60, in_=0, snd=dict(take="clip1/t1", gain_db=0)),
                              dict(id="b", at=60, dur=30, snd=dict(take="missing/take"))],
                       audio=[dict(file=str(tmp / "music.raw"), cdda=True, at=0),
                              dict(file=str(tmp / "voice.wav"), at=30, len_s=0.6)],
                       music=dict(base_db=-12, duck_db=-24, ducks=[[0.0, 1.0]]), loudness=dict(i=-16, tp=-1.5))
            edl["clips"][0]["in"] = edl["clips"][0].pop("in_")
            rep = mix.mix(edl)
            out = tmp / "out" / "t_mix.wav"
            self.assertTrue(out.exists())
            with wave.open(str(out)) as w:
                self.assertEqual(w.getframerate(), 48000)
                self.assertEqual(w.getnchannels(), 2)
                self.assertAlmostEqual(w.getnframes() / 48000, 3.0, delta=0.05)
            self.assertEqual(rep["game_clips"][1]["missing"], "aligned.wav")
            self.assertAlmostEqual(rep["after"]["integrated_lufs"], -16, delta=1.5)
            self.assertLessEqual(rep["after"]["true_peak_dbtp"], -0.5)
            self.assertEqual(len(rep["voices"]), 1)
            self.assertTrue((tmp / "out" / "t_mix_report.json").exists())
            json.loads((tmp / "out" / "t_mix_report.json").read_text())


if __name__ == "__main__":
    unittest.main()
