#!/usr/bin/env python3
"""Client for a Yabasanshiro debug build's MCP control bridge, plus own-window pad input on Windows.

The bridge serves JSON-RPC (MCP streamable HTTP) on a local port: tools such as memory_read, memory_write,
screenshot, and (with a pad patch) pad_set. Tool names depend on your build: call list_tools() first.

Rules this module follows:
- One emulator instance per lane, each with its own port. port_owner() gives the pid listening on a port, so a
  harness can check it drives the instance it started.
- Pad input goes only to the emulator's own window (PostMessage) or through the MCP pad tool. No global input.
- memory_read can answer empty while the core starts or during a long CD read: read() retries.
- memory_write takes bytes as a hex string.

usage: yaba_mcp.py PORT tools              list the bridge's tools
       yaba_mcp.py PORT read ADDR LEN      hex dump (diagnostic)
       yaba_mcp.py PORT owner              pid listening on PORT (Windows netstat)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request


def parse_dump(text: str) -> bytes:
    """memory_read answers hex dump lines: 'ADDRESS: xx xx xx ...'."""
    data = bytearray()
    for line in text.splitlines():
        m = re.match(r"^[0-9A-Fa-f]+:\s+((?:[0-9A-Fa-f]{2} ?)+)", line)
        if m:
            data += bytes(int(p, 16) for p in m.group(1).split())
    return bytes(data)


class Mcp:
    def __init__(self, url: str, timeout: float = 30, client: str = "cps2saturn") -> None:
        self.url, self.timeout, self.client = url, timeout, client
        self.next_id = 0
        self.session: str | None = None

    def _post(self, method: str, params: dict) -> dict:
        self.next_id += 1
        body = json.dumps({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self.session = sid
            text = resp.read().decode()
        for line in text.splitlines():
            if line.startswith("data:"):
                text = line[5:].strip()
                break
        return json.loads(text) if text.strip() else {}

    def initialize(self) -> None:
        self._post("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": self.client, "version": "1"}})
        self._post("notifications/initialized", {})

    def list_tools(self) -> list[str]:
        r = self._post("tools/list", {})
        return [t["name"] for t in r.get("result", {}).get("tools", [])]

    def call(self, name: str, **arguments) -> str:
        r = self._post("tools/call", {"name": name, "arguments": arguments})
        if "error" in r:
            raise RuntimeError(f"{name}: {r['error']}")
        res = r.get("result", {})
        if res.get("isError"):
            raise RuntimeError(f"{name}: " + " ".join(i.get("text", "") for i in res.get("content", [])))
        return "\n".join(i.get("text", "") for i in res.get("content", []))

    def read(self, address: int, length: int, tries: int = 600, wait: float = 0.1) -> bytes:
        last: Exception | None = None
        for _ in range(tries):
            try:
                data = parse_dump(self.call("memory_read", address=hex(address), length=int(length)))
                if len(data) >= length:
                    return data[:length]
                last = RuntimeError(f"short read {len(data)} of {length}")
            except RuntimeError as e:
                last = e
            time.sleep(wait)
        raise RuntimeError(f"memory_read {address:#x}: {last}")

    def write(self, address: int, data: bytes) -> str:
        return self.call("memory_write", address=hex(address), bytes=data.hex())


def port_owner(port: int) -> int | None:
    """pid listening on 127.0.0.1:port, from netstat (Windows). None when free or unknown."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
    except OSError:
        return None
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 5 and p[1].endswith(f":{port}") and p[3] == "LISTENING":
            return int(p[4])
    return None


class WindowPad:
    """Key messages to one process's own window. Windows only. Keys are virtual-key codes from your ini."""

    WM_KEYDOWN, WM_KEYUP = 0x100, 0x101

    def __init__(self, pid: int, keys: dict[str, int]) -> None:
        import ctypes
        import ctypes.wintypes as wt
        self.ct, self.wt = ctypes, wt
        self.u32 = ctypes.WinDLL("user32", use_last_error=True)
        self.u32.PostMessageW.argtypes = (wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self.keys = keys
        self.hwnd = self._main_window(pid)
        self.down: set[str] = set()

    def _main_window(self, pid: int):
        ct, wt, u32 = self.ct, self.wt, self.u32
        found = []
        enum = ct.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def cb(h, _):
            p = wt.DWORD()
            u32.GetWindowThreadProcessId(h, ct.byref(p))
            if p.value == pid and u32.IsWindowVisible(h):
                r = wt.RECT()
                u32.GetWindowRect(h, ct.byref(r))
                found.append(((r.right - r.left) * (r.bottom - r.top), h))
            return True
        u32.EnumWindows(enum(cb), 0)
        if not found:
            raise RuntimeError(f"no visible window for pid {pid}")
        return max(found)[1]

    def key(self, name: str, down: bool) -> None:
        vk = self.keys[name]
        scan = self.u32.MapVirtualKeyW(vk, 0)
        lp = 1 | (scan << 16) | (0 if down else (3 << 30))
        if not self.u32.PostMessageW(self.hwnd, self.WM_KEYDOWN if down else self.WM_KEYUP, vk, lp):
            raise OSError(self.ct.get_last_error())

    def set(self, names) -> None:
        names = set(names)
        for n in list(self.down - names):
            self.key(n, False)
            self.down.discard(n)
        for n in names - self.down:
            self.key(n, True)
            self.down.add(n)


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    port, cmd = int(a[0]), a[1]
    if cmd == "owner":
        print(port_owner(port))
        return 0
    m = Mcp(f"http://127.0.0.1:{port}/mcp")
    m.initialize()
    if cmd == "tools":
        print("\n".join(m.list_tools()))
    elif cmd == "read":
        print(m.read(int(a[2], 16), int(a[3], 0)).hex())
    return 0


if __name__ == "__main__":
    sys.exit(main())
