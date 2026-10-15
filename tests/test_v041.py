import http.server
import shutil
from pathlib import Path
import os
import tempfile
import threading
import unittest
import urllib.error

import helpers
from watchcats import api, fonts
from watchcats.ingest import Ingestor
from watchcats.live import LiveWindow
from watchcats.parser import parse_error_line, parse_tz
from watchcats.runtime import Collector, Hub
from watchcats.storage import Storage


class FakeSampler:
    def __init__(self, rx, tx):
        self.rx, self.tx = rx, tx

    def sample(self):
        return {"cpu": {"pct": 1, "cores": 2}, "ram": {"total": 1, "used": 1, "pct": 1},
                "net": {"iface": "x", "rx_mbps": self.rx, "tx_mbps": self.tx, "link_mbps": 1000},
                "disk": {"path": "/", "total": 1, "used": 1, "free": 0, "pct": 1, "read_mb_s": 0, "write_mb_s": 0}}


class GaugeSplitTests(unittest.TestCase):
    def snapshot(self, rx, tx):
        with tempfile.TemporaryDirectory() as d:
            st = Storage(os.path.join(d, "w.db"))
            c = Collector(None, FakeSampler(rx, tx), LiveWindow(), None, Hub())
            snap = c.build(st)
            st.close()
        return snap["live"]

    def test_first_download_is_all_fill_not_serve(self):
        # a MISS is proxied: ~241 Mbps comes in from the internet and ~243 Mbps goes out to the client
        live = self.snapshot(rx=241.0, tx=243.0)
        self.assertEqual(live["fill_mbps"], 241.0)
        self.assertEqual(live["serve_mbps"], 2.0)

    def test_pure_cache_hit_is_all_serve(self):
        live = self.snapshot(rx=0.0, tx=800.0)
        self.assertEqual((live["fill_mbps"], live["serve_mbps"]), (0.0, 800.0))

    def test_serve_never_negative(self):
        self.assertEqual(self.snapshot(rx=300.0, tx=100.0)["serve_mbps"], 0.0)


class XboxHeuristicTests(unittest.TestCase):
    def test_unrecognised_client_on_xbox_cdn_is_a_console(self):
        with tempfile.TemporaryDirectory() as d:
            line = '[%s] %s / - - - [05/Oct/2026:15:05:49 +0330] "GET /x HTTP/1.1" 200 1000 "-" "%s" "HIT" "assets1.xboxlive.com" "-"\n'
            with open(os.path.join(d, "access.log"), "w") as f:
                f.write(line % ("xboxlive", "192.168.1.122", "Weird/1.0"))
                f.write(line % ("steam", "192.168.1.200", "Weird/1.0"))
                f.write(line % ("xboxlive", "192.168.1.101", "Microsoft-Delivery-Optimization/10.0"))
            ing = Ingestor(Storage(os.path.join(d, "w.db")), d, None, "UTC")
            ing.poll()
            kinds = {x["ip"]: x["kind"] for x in ing.storage.devices()}
        self.assertEqual(kinds["192.168.1.122"], "xbox_console")
        self.assertEqual(kinds["192.168.1.200"], "unknown")
        self.assertEqual(kinds["192.168.1.101"], "windows")  # a known Windows User-Agent still wins


class MoreErrorKindsTests(unittest.TestCase):
    def kind(self, msg):
        line = '2026/10/04 17:14:43 [error] 1#1: *1 %s, client: 1.1.1.1, server: , request: "GET /a HTTP/1.1", host: "h"' % msg
        return parse_error_line(line, parse_tz("UTC")).kind

    def test_typical_nginx_messages(self):  # wording taken from nginx's usual error texts, not from this server's logs
        self.assertEqual(self.kind("no live upstreams while connecting to upstream"), "upstream_unavailable")
        self.assertEqual(self.kind("connect() failed (111: Connection refused) while connecting to upstream"), "upstream_connect_failed")
        self.assertEqual(self.kind("upstream prematurely closed connection while reading response header from upstream"), "upstream_closed")
        self.assertEqual(self.kind("recv() failed (104: Connection reset by peer) while reading response header from upstream"), "upstream_reset")
        self.assertEqual(self.kind("something nobody has seen before"), "other")
        self.assertEqual(self.kind("unexpected status code 504 in slice response while reading response header from upstream"), "upstream_504")


class FontInstallTests(unittest.TestCase):
    def serve(self, body, code=200):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        return "http://127.0.0.1:%d/font.woff2" % srv.server_address[1]

    def test_valid_font_is_written(self):
        url = self.serve(b"wOF2" + b"\0" * 30000)
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "fonts", "Vazirmatn.woff2")
            self.assertEqual(fonts.install(url, dest), 30004)
            self.assertTrue(os.path.exists(dest))

    def test_html_or_tiny_file_is_rejected_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "f.woff2")
            with self.assertRaises(ValueError):
                fonts.install(self.serve(b"<html>not a font</html>"), dest)
            with self.assertRaises(ValueError):
                fonts.install(self.serve(b"wOF2tiny"), dest)
            self.assertFalse(os.path.exists(dest))

    def test_http_error_is_raised(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(urllib.error.HTTPError):
                fonts.install(self.serve(b"nope", 404), os.path.join(d, "f.woff2"))


class StyleFontTests(unittest.TestCase):
    def test_font_face_only_when_the_font_is_installed(self):
        with tempfile.TemporaryDirectory() as d:
            web = Path(d)
            shutil.copy(api.WEB / "style.css", web / "style.css")
            self.assertNotIn("@font-face", api.style_css(web))
            (web / "fonts").mkdir()
            (web / "fonts" / "Vazirmatn.woff2").write_bytes(b"wOF2")
            css = api.style_css(web)
            self.assertTrue(css.startswith("@font-face"))
            self.assertIn("/static/fonts/Vazirmatn.woff2", css)
            self.assertIn(":root", css)


if __name__ == "__main__":
    unittest.main()
