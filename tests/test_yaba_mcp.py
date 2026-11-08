import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import _util  # noqa: F401
import yaba_mcp

RAM = {0x1000 + i: i for i in range(16)}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        m, p = req["method"], req.get("params", {})
        if m == "tools/list":
            res = {"tools": [{"name": "memory_read"}, {"name": "memory_write"}]}
        elif m == "tools/call" and p["name"] == "memory_read":
            a, n = int(p["arguments"]["address"], 16), p["arguments"]["length"]
            res = {"content": [{"type": "text", "text": f"{a:08x}: " + " ".join(f"{RAM.get(a + i, 0):02x}" for i in range(n))}]}
        elif m == "tools/call" and p["name"] == "memory_write":
            a, data = int(p["arguments"]["address"], 16), bytes.fromhex(p["arguments"]["bytes"])
            for i, v in enumerate(data):
                RAM[a + i] = v
            res = {"content": [{"type": "text", "text": "ok"}]}
        else:
            res = {}
        body = json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": res}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "s1")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class YabaMcpTest(unittest.TestCase):
    def test_against_fake_bridge(self):
        srv = HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            m = yaba_mcp.Mcp(f"http://127.0.0.1:{srv.server_port}/mcp", timeout=5)
            m.initialize()
            self.assertEqual(m.session, "s1")
            self.assertIn("memory_read", m.list_tools())
            self.assertEqual(m.read(0x1000, 4), bytes([0, 1, 2, 3]))
            m.write(0x1002, b"\xaa")
            self.assertEqual(m.read(0x1002, 1, tries=1), b"\xaa")
        finally:
            srv.shutdown()

    def test_parse_dump(self):
        self.assertEqual(yaba_mcp.parse_dump("00001000: 01 02\n00001002: ff"), b"\x01\x02\xff")


if __name__ == "__main__":
    unittest.main()
