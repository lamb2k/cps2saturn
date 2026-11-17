#!/usr/bin/env python3
"""The CPS tile packer under its old name, kept for existing scripts. See cps_tiles.py."""
import sys

from cps_tiles import *  # noqa: F401,F403
from cps_tiles import main

if __name__ == "__main__":
    sys.exit(main())
