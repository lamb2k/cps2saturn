"""Shared test helpers: tools on the path, a temp folder, the example config."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
EXAMPLE = ROOT / "configs" / "avspu.example.yaml"
sys.path.insert(0, str(TOOLS))
