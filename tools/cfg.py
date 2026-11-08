#!/usr/bin/env python3
"""Per-game config loader. Every tool reads game constants from here, never from its own code.

Uses PyYAML when installed. Otherwise a small reader covers the subset the example uses: nested maps by
indentation, '- item' lists, inline [a, b] lists, ints (decimal or 0x hex), quoted or bare strings, true/false,
and '# comments'. ${NAME} in strings expands from the environment (empty when unset).

usage: cfg.py CONFIG [dotted.key]   prints the whole config as JSON, or one value
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from typing import Any


def _scalar(s: str) -> Any:
    s = s.strip()
    if not s:
        return None
    if s[0] in "\"'" and s[-1] == s[0]:
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        return _inline_list(s[1:-1])
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    try:
        return int(s, 0)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def _inline_list(body: str) -> list:
    out, depth, cur = [], 0, ""
    for ch in body:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(_scalar(cur))
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(_scalar(cur))
    return out


def _strip_comment(line: str) -> str:
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def parse_mini_yaml(text: str) -> Any:
    lines = []
    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if line.strip():
            lines.append((len(line) - len(line.lstrip(" ")), line.strip()))

    def block(i: int, indent: int) -> tuple[Any, int]:
        if i < len(lines) and lines[i][1].startswith("- "):
            out = []
            while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                out.append(_scalar(lines[i][1][2:]))
                i += 1
            return out, i
        out: dict = {}
        while i < len(lines) and lines[i][0] == indent:
            key, _, rest = lines[i][1].partition(":")
            i += 1
            if rest.strip():
                out[key.strip()] = _scalar(rest)
            elif i < len(lines) and lines[i][0] > indent:
                out[key.strip()], i = block(i, lines[i][0])
            else:
                out[key.strip()] = None
        return out, i

    if not lines:
        return {}
    value, _ = block(0, lines[0][0])
    return value


def _expand(v: Any) -> Any:
    if isinstance(v, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m[1], ""), v)
    if isinstance(v, list):
        return [_expand(x) for x in v]
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    return v


def load(path: str | os.PathLike) -> dict:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
    except ImportError:
        data = parse_mini_yaml(text)
    return _expand(data or {})


def get(cfg: dict, dotted: str, default: Any = None) -> Any:
    cur: Any = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


if __name__ == "__main__":
    c = load(sys.argv[1])
    print(json.dumps(get(c, sys.argv[2]) if len(sys.argv) > 2 else c, indent=2))
