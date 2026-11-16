#!/usr/bin/env python3
"""The CPS object tool under its old name, kept for existing scripts. See cps_objects.py."""
import sys

from cps_objects import *  # noqa: F401,F403
from cps_objects import main

if __name__ == "__main__":
    sys.exit(main())
