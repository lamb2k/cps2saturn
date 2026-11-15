import contextlib
import io
import json
import pathlib
import re
import tempfile
import unittest

import _util  # noqa: F401

_util.sys.path.insert(0, str(_util.TOOLS / "clip"))
import cfg  # noqa: E402
import shot_script as ss  # noqa: E402

VB, STATE, HEALTH, NEED = 0x100, 0x200, 0x300, 0x400
IDLE, BUSY = bytes.fromhex("020000"), bytes.fromhex("030000")


class FakePad:
    """Records key sets and makes the fake game's player state follow them."""

    def __init__(self, emu):
        self.emu, self.calls = emu, []

    def set(self, names):
        self.calls.append(sorted(names))
        self.emu.ram[STATE:STATE + 3] = BUSY if "a" in names else IDLE


class FakeEmu:
    """Stands in for yaba_mcp.Mcp: a vblank counter that runs while unpaused, paused one-frame stepping, states."""

    def __init__(self):
        self.ram = bytearray(0x1000)
        self.ram[STATE:STATE + 3] = IDLE
        self.paused = False
        self.saved = {}
        self.calls = []
        self.busy_frames = 0     # the player stays busy for this many stepped frames

    def counter(self):
        return int.from_bytes(self.ram[VB:VB + 4], "big")

    def set_counter(self, v):
        self.ram[VB:VB + 4] = v.to_bytes(4, "big")

    def read(self, addr, n, **kw):
        if addr == VB and not self.paused:
            self.set_counter(self.counter() + 1)       # time passes while the core runs
        return bytes(self.ram[addr:addr + n])

    def write(self, addr, data):
        self.ram[addr:addr + len(data)] = data
        return "ok"

    def call(self, name, **kw):
        self.calls.append((name, kw))
        if name == "pause":
            self.paused = True
        elif name == "resume":
            self.paused = False
        elif name == "framebuffer_screenshot":
            pathlib.Path(kw["path"]).write_bytes(b"png")
        elif name == "framebuffer_burst":
            d = pathlib.Path(kw["directory"])
            for i in range(kw["frames"]):
                (d / ("%s%04d.png" % (kw["prefix"], i))).write_bytes(b"png")
            self.set_counter(self.counter() + kw["frames"])
            if self.busy_frames:
                self.busy_frames = max(0, self.busy_frames - kw["frames"])
                if not self.busy_frames:
                    self.ram[STATE:STATE + 3] = IDLE
        elif name == "save_state":
            self.saved[kw["slot"]] = (self.counter(), bytes(self.ram))
            return "saved"
        elif name == "load_state":
            self.ram[:] = self.saved[kw["slot"]][1]
            return "loaded"
        return "ok"


CAP = {"vblank": {"addr": VB, "bytes": 4}, "idle": {"addr": STATE, "bytes": 3, "states": ["020000"]},
       "health": {"addr": HEALTH, "bytes": 2}, "port": 9790, "pad_mode": "window", "keys": {"a": 71}}


def shooter(tmp, emu=None, spec=None, cap=None):
    emu = emu or FakeEmu()
    pad = FakePad(emu)
    sh = ss.Shooter(emu, pad, cap or CAP, pathlib.Path(tmp), spec or {"build": "synthetic"}, log=lambda *a: None,
                    poll_s=0, sleep=lambda s: None)
    return sh, emu, pad


class RouteTest(unittest.TestCase):
    def test_route_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            sh, emu, pad = shooter(tmp)
            sh.route(["w:5", "t:a:3:4", "p:look", "hp:101", "save:2", "step:2", "ge:0x100:6", "in:0x100:0:999999",
                      "need0:0x400:1", "need1:0x400:0", "needeq:0x400:0", "press:a", "release", "idle:20"])
            self.assertGreaterEqual(emu.counter(), 5)
            self.assertIn(["a"], pad.calls)
            self.assertEqual(pad.calls[-1], [])
            self.assertTrue((pathlib.Path(tmp) / "route" / "02_look.png").exists())
            self.assertEqual(int.from_bytes(emu.ram[HEALTH:HEALTH + 2], "big"), 101)
            self.assertEqual(sh.assists[0]["kind"], "health_set")
            self.assertTrue(sh.assists[0]["staged"])
            self.assertIn(2, emu.saved)

    def test_repeat_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            sh, _emu, pad = shooter(tmp)
            sh.route([{"repeat": 3, "steps": ["t:a:1:1"]}])
            self.assertEqual(pad.calls.count(["a"]), 3)

    def test_need_aborts(self):
        with tempfile.TemporaryDirectory() as tmp:
            sh, emu, _pad = shooter(tmp, spec={"route": ["need0:0x400:1"], "out": tmp})
            emu.ram[NEED] = 0
            emu.ram[NEED + 3] = 1
            with self.assertRaises(ss.CaptureAbort):
                sh.run()
            self.assertTrue((pathlib.Path(tmp) / "ABORTED").exists())

    def test_wait_times_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = [0.0]
            emu = FakeEmu()
            emu.paused = True       # the counter never moves
            sh = ss.Shooter(emu, FakePad(emu), CAP, pathlib.Path(tmp), {"wait_max_s": 5}, log=lambda *a: None,
                            clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + 1))
            self.assertFalse(sh.wait_until(10, "stuck"))

    def test_syntax(self):
        self.assertEqual(ss.validate_route(["w:1", {"repeat": 2, "steps": ["r:1", "release"]}]), 5)
        for bad in (["nope:1"], ["w"], [{"repeat": 0, "steps": []}], [5]):
            with self.assertRaises(SystemExit):
                ss.validate_route(bad)

    def test_addresses(self):
        self.assertEqual(ss.parse_addr(0x10), 0x10)
        self.assertEqual(ss.parse_addr("ff"), 0xff)
        self.assertEqual(ss.parse_addr("sym:counter+0x8", {"counter": 0x1000}), 0x1008)
        with self.assertRaises(SystemExit):
            ss.parse_addr("sym:missing", {})


class TakeTest(unittest.TestCase):
    def test_take_chunks_and_disclosure(self):
        with tempfile.TemporaryDirectory() as tmp:
            sh, emu, _pad = shooter(tmp)
            t = {"id": "a", "frames": 25, "schedule": [[0, []], [12, ["a"]], [15, []]], "health": 101}
            data = sh.take(t, None)
            d = pathlib.Path(tmp) / "a"
            self.assertEqual(len(list(d.glob("f*.png"))), 25)
            self.assertFalse((d / "_burst").exists())
            tj = json.loads((d / "take.json").read_text())
            self.assertEqual([e["n"] for e in tj["trace"]], [10, 2, 3, 10])
            self.assertEqual(tj["trace"][2]["keys"], ["a"])
            self.assertEqual(tj["trace"][2]["state"], "030000")
            self.assertEqual(tj["build"], "synthetic")
            self.assertTrue(tj["staged"])
            self.assertEqual(tj["assists"][0]["kind"], "health_hold")
            self.assertEqual(tj["assists"][0]["chunks"], 4)
            self.assertIn("health was held at 101", tj["disclose"][0])
            self.assertEqual(int.from_bytes(emu.ram[HEALTH:HEALTH + 2], "big"), 101)
            self.assertEqual(data["frames"], 25)
            sh.save_assists()
            self.assertIn("held at 101", ss.disclosures(tmp)[0])

    def test_unstaged_take_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            sh, _emu, _pad = shooter(tmp)
            sh.take({"id": "b", "frames": 3}, None)
            tj = json.loads((pathlib.Path(tmp) / "b" / "take.json").read_text())
            self.assertFalse(tj["staged"])
            self.assertEqual(tj["assists"], [])

    def test_take_reloads_state_and_pre_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            emu = FakeEmu()
            emu.ram[STATE:STATE + 3] = BUSY
            emu.busy_frames = 3
            sh, emu, _pad = shooter(tmp, emu=emu, spec={"slot": 1})
            emu.saved[1] = (0, bytes(emu.ram))
            sh.take({"id": "c", "frames": 4, "pre_idle": 10}, 1)
            names = [c[0] for c in emu.calls]
            self.assertIn("load_state", names)
            self.assertEqual(len(list((pathlib.Path(tmp) / "c").glob("f*.png"))), 4)
            pre = [c for c in emu.calls if c[1].get("prefix", "").startswith("pre")]
            self.assertEqual(len(pre), 3)      # stepped until the player stood free

    def test_probes(self):
        cap = dict(CAP, enemy_pool={"base": 0x500, "count": 3, "stride": 8, "health_offset": 2, "health_bytes": 2},
                   player_block={"base": 0x600, "size": 4})
        with tempfile.TemporaryDirectory() as tmp:
            sh, emu, _pad = shooter(tmp, cap=cap)
            for i in range(3):
                emu.ram[0x500 + i * 8 + 2:0x500 + i * 8 + 4] = (10 * (i + 1)).to_bytes(2, "big")
            sh.take({"id": "p", "frames": 2, "probe_enemies": True, "probe_player": True}, None)
            tj = json.loads((pathlib.Path(tmp) / "p" / "take.json").read_text())
            self.assertEqual(tj["trace"][0]["enemy_hp"], [10, 20, 30])
            self.assertEqual(tj["trace"][0]["player_blk"], "00000000")


class LauncherTest(unittest.TestCase):
    def config(self, emu_dir):
        return {"capture": {"emulator_dir": pathlib.Path(emu_dir).as_posix(), "port": 9790, "keys": {"a": 71},
                            "vblank": {"addr": 0x100}}}

    def test_settings_need_the_game_constants(self):
        with self.assertRaises(SystemExit):
            ss.capture_settings({"capture": {}})
        ss.capture_settings({"capture": {}}, need_game=False)
        self.assertEqual(ss.capture_settings(self.config("."))["pad_mode"], "window")

    def test_example_config_has_capture_section(self):
        c = cfg.load(_util.EXAMPLE)
        cap = ss.capture_settings(c, need_game=False)
        self.assertEqual(cap["pad_mode"], "window")

    def test_refuses_a_folder_without_the_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini = pathlib.Path(tmp) / "yabause.ini"
            with self.assertRaises(SystemExit):
                ss.check_own_copy(pathlib.Path(tmp), ini)
            (pathlib.Path(tmp) / ss.MARKER).write_text("")
            ss.check_own_copy(pathlib.Path(tmp), ini)
            with self.assertRaises(SystemExit):
                ss.check_own_copy(pathlib.Path(tmp), pathlib.Path(tmp) / "sub" / "yabause.ini")

    def test_ini_patch_touches_only_listed_keys(self):
        text = "[General]\r\nDebug\\McpServerPort=1\r\nDebug\\McpServerEnabled=false\r\nGeneral\\UseSh2Cache=true\r\n" \
               "General\\CdRomISO=x\r\nSound\\SoundCore=2\r\nautostart=false\r\nOther=keep\r\n"
        want = ss.ini_changes({"port": 9790}, {"cue": "disc/a.cue"})
        out = ss.patch_ini(text, want)
        self.assertIn("Debug\\McpServerPort=9790", out)
        self.assertIn("General\\UseSh2Cache=false", out)
        self.assertIn("Sound\\SoundCore=0", out)
        self.assertIn("Other=keep", out)
        self.assertEqual(ss.ini_changes({"port": 1}, {"cue": "c", "sh2cache": True})["General\\UseSh2Cache"], "true")
        with self.assertRaises(SystemExit):
            ss.patch_ini("[General]\n", want)

    def test_dry_run_starts_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            emu_dir = pathlib.Path(tmp) / "emu"
            emu_dir.mkdir()
            (emu_dir / ss.MARKER).write_text("")
            cfg_path = pathlib.Path(tmp) / "g.yaml"
            cfg_path.write_text("capture:\n  emulator_dir: '%s'\n  port: 9790\n  vblank:\n    addr: 0x100\n" % emu_dir.as_posix())
            spec = {"name": "t", "cue": "none.cue", "out": (pathlib.Path(tmp) / "out").as_posix(), "route": ["w:1", "t:a"],
                    "takes": [{"id": "a", "frames": 1}]}
            spec_path = pathlib.Path(tmp) / "s.json"
            spec_path.write_text(json.dumps(spec))
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                self.assertEqual(ss.main(["--config", str(cfg_path), str(spec_path), "--dry-run"]), 0)
            self.assertIn("UseSh2Cache=false", buf.getvalue())
            self.assertFalse((pathlib.Path(tmp) / "out").exists())


class RulesTest(unittest.TestCase):
    def test_no_global_input_in_the_clip_tools(self):
        banned = ["Send" + "Input", "keybd" + "_event", "Send" + "Keys", "pyauto" + "gui", "mouse" + "_event", "SetForeground" + "Window"]
        for p in (_util.TOOLS / "clip").glob("*.py"):
            text = p.read_text(encoding="utf-8")
            for b in banned:
                self.assertNotIn(b, text, f"{p.name} mentions {b}")

    def test_no_game_constants_in_the_tool(self):
        text = (_util.TOOLS / "clip" / "shot_script.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"0x[0-9a-fA-F]{6,}", text), "an address-like literal is in shot_script.py")


if __name__ == "__main__":
    unittest.main()
