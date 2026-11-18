import io
import pathlib
import sys
import tempfile
import unittest

import _util  # noqa: F401
import ymir_misalign_gate as g

# Synthetic lines in the log format. Example addresses only.
CLEAN = """\
READ SH2-M PC=0600A002 addr=0600A002 32-bit
READ SH2-S PC=0600B006 addr=0600B006 16-bit
junk line that is not a log line
"""
DIRTY = CLEAN + """\
READ SH2-M PC=060A128E addr=060A1292 32-bit
WRITE SH2-S PC=0600C112 addr=0600D001 16-bit
"""


class MisalignGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.write_text(text)
        return str(p)

    def main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        old = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            rc = g.main(list(args))
        finally:
            sys.stdout, sys.stderr = old
        return rc, out.getvalue(), err.getvalue()

    def test_instruction_fetch_lines_are_filtered(self):
        fetch, data = g.parse(CLEAN)
        self.assertEqual((fetch, len(data)), (2, 0))

    def test_clean_log_passes_and_dirty_log_fails(self):
        rc, out, _ = self.main("--check", self.write("clean.log", CLEAN))
        self.assertEqual(rc, 0)
        self.assertIn("0 hits", out)
        rc, out, _ = self.main("--check", self.write("dirty.log", DIRTY))
        self.assertEqual(rc, 1)
        self.assertIn("PC=060A128E addr=060A1292 32-bit", out)
        self.assertIn("WRITE SH2-S PC=0600C112", out)

    def test_allowlist_clears_a_reviewed_pc_and_reports_stale_entries(self):
        allow = self.write("allow.txt", "# reviewed\n060A128E byte table read as longs on purpose, owner A\n0600DEAD gone code\n")
        rc, out, _ = self.main("--check", self.write("d.log", DIRTY), "--allow", allow)
        self.assertEqual(rc, 1)                       # the WRITE at 0600C112 is still a hit
        self.assertIn("1 allowed, 1 hits", out)
        self.assertIn("STALE allowlist PC 0600DEAD", out)
        both = self.write("both.txt", "060A128E reason one\n0600C112 reason two\n")
        self.assertEqual(self.main("--check", self.write("d2.log", DIRTY), "--allow", both)[0], 0)

    def test_allowlist_needs_a_reason_and_a_hex_pc(self):
        for text in ("060A128E\n", "ZZZZ reason\n"):
            rc, _, err = self.main("--check", self.write("c.log", CLEAN), "--allow", self.write("a.txt", text))
            self.assertEqual(rc, 2)
            self.assertIn("bad input", err)

    def test_positive_control_flips_the_meaning(self):
        self.assertEqual(self.main("--check", self.write("d.log", DIRTY), "--expect-hits")[0], 0)
        rc, out, _ = self.main("--check", self.write("c.log", CLEAN), "--expect-hits")
        self.assertEqual(rc, 1)
        self.assertIn("NO data accesses", out)

    def test_missing_log_is_bad_input(self):
        rc, _, err = self.main("--check", str(self.dir / "nope.log"))
        self.assertEqual(rc, 2)
        self.assertIn("cannot read log", err)

    def test_run_checks_the_log_the_program_writes(self):
        log = str(self.dir / "run.log")
        script = self.dir / "fake_emulator.py"
        script.write_text("import sys\nopen(sys.argv[1], 'w').write(%r)\n" % DIRTY)
        rc, out, _ = self.main("--run", "--exe", sys.executable, "--cmd-args", '"%s" {log}' % script, "--log", log, "--secs", "5")
        self.assertEqual(rc, 1)
        self.assertIn("2 hits", out)

    def test_run_without_a_log_is_an_error(self):
        log = str(self.dir / "none.log")
        script = self.dir / "fake_emulator.py"
        script.write_text("pass\n")
        rc, _, err = self.main("--run", "--exe", sys.executable, "--cmd-args", '"%s"' % script, "--log", log, "--secs", "5")
        self.assertEqual(rc, 2)
        self.assertIn("wrote nothing", err)

    def test_run_needs_exe_and_log(self):
        self.assertEqual(self.main("--run")[0], 2)


if __name__ == "__main__":
    unittest.main()
