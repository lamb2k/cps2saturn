#!/usr/bin/env python3
"""Check a declared matrix of paired MAME golden captures.

Under each capture root, store one golden as ROUTE/DELAY.bin for every requested
pair. DELAY is a run label such as d0. Use the same capture start, duration,
format, and game configuration on both sides.
"""
import argparse
import pathlib

import cfg
from golden_reader import compare, sizes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=pathlib.Path)
    parser.add_argument("candidate", type=pathlib.Path)
    parser.add_argument("--routes", nargs="+", required=True)
    parser.add_argument("--delays", nargs="+", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--delta", action="store_true", help="both sides use the delta format")
    args = parser.parse_args(argv)
    for labels in (args.routes, args.delays):
        if len(labels) != len(set(labels)):
            parser.error("each route and delay label must be unique within its list")
        if any(label in {"", ".", ".."} or pathlib.PureWindowsPath(label).name != label
               or "/" in label for label in labels):
            parser.error("each route and delay label must be a single filename component")
    base, ws, os_ = sizes(cfg.load(args.config))
    matches = 0
    for route in args.routes:
        for delay in args.delays:
            path = pathlib.Path(route) / f"{delay}.bin"
            ref, candidate = args.reference / path, args.candidate / path
            try:
                if ref.samefile(candidate):
                    raise ValueError("reference and candidate are the same file")
                ok, message = compare(ref, candidate, base, ws, os_, args.delta)
            except (OSError, ValueError) as exc:
                ok, message = False, str(exc)
            print(f"{route} {delay} {'PASS' if ok else 'FAIL'}  {message}")
            matches += ok
    total = len(args.routes) * len(args.delays)
    print(f"{matches}/{total} pairs matched on IRQ and work/object RAM")
    return 0 if matches == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
