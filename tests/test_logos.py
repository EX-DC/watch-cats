import http.client
import os
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import helpers  # noqa: F401
from test_web import env
from watchcats import api, logos

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0h24v24H0z"/></svg>'


class InstallLogosTests(unittest.TestCase):
    def test_copies_known_icons_and_rejects_unsafe_ones(self):
        with tempfile.TemporaryDirectory() as d:
            src, dest = Path(d) / "icons", Path(d) / "logos"
            src.mkdir()
            (src / "steam.svg").write_text(SVG)
            (src / "playstation.svg").write_text(SVG)
            (src / "windows.svg").write_text(SVG)
            (src / "epicgames.svg").write_text(SVG.replace("<path", "<script>alert(1)</script><path"))
            (src / "xbox.svg").write_text("not an svg at all")
            copied, missing = logos.install(src, dest)
            self.assertEqual(set(copied), {"steam", "sony", "wsus"})
            for k in ("epicgames", "xboxlive", "riot"):
                self.assertIn(k, missing)
            self.assertEqual(sorted(p.name for p in dest.iterdir()), ["sony.svg", "steam.svg", "wsus.svg"])


class MonoDetectionTests(unittest.TestCase):
    def mono(self, text):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.svg"
            f.write_text(text)
            return api._svg_is_mono(f)

    def test_one_colour_icons_are_mono_and_coloured_ones_are_not(self):
        self.assertTrue(self.mono(SVG))
        self.assertTrue(self.mono('<svg role="img" fill="currentColor" viewBox="0 0 24 24"><title>x</title><path d="M0 0"/></svg>'))
        self.assertTrue(self.mono('<svg fill="none"><path d="M0 0"/></svg>'))
        self.assertFalse(self.mono('<svg><path d="M0 0" fill="#00a4ef"/></svg>'))
        self.assertFalse(self.mono('<svg><rect width="24" height="24"/><path d="M0 0"/></svg>'))
        self.assertFalse(self.mono('<svg><style>.a{fill:red}</style><path class="a" d="M0 0"/></svg>'))
        self.assertFalse(self.mono('<svg><defs><linearGradient id="g"/></defs><path d="M0 0"/></svg>'))


class LogoApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        web = Path(self.tmp.name) / "web"
        shutil.copytree(api.WEB, web, ignore=shutil.ignore_patterns("logos", "fonts"))
        (web / "logos").mkdir()
        (web / "logos" / "steam.svg").write_text(SVG)
        (web / "logos" / "riot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        (web / "logos" / "bad name.svg").write_text(SVG)
        (web / "logos" / "x.exe").write_text("x")
        (web / "logos" / "Nintendo.svg").write_text(SVG)  # a capital letter in the file name is accepted
        (web / "logos" / "wsus.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" fill="#fff"/><path d="M0 0h9v9H0z" fill="#f25022"/></svg>')
        self.orig, api.WEB = api.WEB, web  # the API reads this module variable on every request
        self.tmp_env, self.srv, self.hub, self.base = env()

    def tearDown(self):
        api.WEB = self.orig
        self.srv.shutdown()
        self.tmp_env.cleanup()
        self.tmp.cleanup()

    def get(self, path, method="GET"):
        req = urllib.request.Request(self.base + path, method=method)
        return urllib.request.urlopen(req, timeout=5)

    def test_listing_only_valid_files(self):
        import json
        self.assertEqual(json.loads(self.get("/api/logos").read()), {"logos": {
            "nintendo": {"ext": "svg", "mono": True}, "riot": {"ext": "png", "mono": False},
            "steam": {"ext": "svg", "mono": True},
            "wsus": {"ext": "svg", "mono": False}}})  # wsus has its own colours and background: shown as it is

    def test_logo_is_served_with_a_sandboxing_csp(self):
        with self.get("/static/logos/steam.svg") as r:
            self.assertEqual(r.headers["Content-Type"], "image/svg+xml")
            self.assertIn("sandbox", r.headers["Content-Security-Policy"])
            self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(r.read().decode(), SVG)
        with self.get("/static/logos/riot.png") as r:
            self.assertEqual(r.headers["Content-Type"], "image/png")
        for name in ("nintendo.svg", "Nintendo.svg"):  # lower-case key finds the capitalised file
            with self.get("/static/logos/" + name) as r:
                self.assertEqual(r.status, 200, name)
                self.assertEqual(r.read().decode(), SVG)

    def test_nothing_else_is_served(self):
        for path in ("/static/logos/x.exe", "/static/logos/..%2fapi.py", "/static/logos/bad%20name.svg",
                     "/static/logos/nothere.svg", "/static/logos/", "/static/logos/steam.svg/extra",
                     "/static/logos/steam.png"):  # wrong extension for an existing key
            with self.assertRaises(urllib.error.HTTPError, msg=path) as cm:
                self.get(path)
            self.assertEqual(cm.exception.code, 404, path)

    def test_head_requests_have_headers_but_no_body(self):
        for path in ("/api/version", "/", "/static/logos/steam.svg", "/api/logos"):
            with self.get(path, "HEAD") as r:
                self.assertEqual(r.status, 200, path)
                self.assertGreater(int(r.headers["Content-Length"]), 0, path)
                self.assertEqual(r.read(), b"", path)
        host, port = self.base.replace("http://", "").split(":")
        c = http.client.HTTPConnection(host, int(port), timeout=5)
        c.request("HEAD", "/api/stream")
        self.assertEqual(c.getresponse().status, 200)  # returns immediately instead of streaming
        c.close()


if __name__ == "__main__":
    unittest.main()
