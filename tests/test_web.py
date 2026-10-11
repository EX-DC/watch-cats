import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import helpers
from watchcats.api import make_server, parse_allow
from watchcats.domains import DomainMap
from watchcats.ingest import Ingestor
from watchcats.live import LiveWindow
from watchcats.parser import parse_access_line
from watchcats.runtime import Collector, Hub
from watchcats.storage import Storage
from watchcats.sysmetrics import SystemSampler, local_ips


def env(hide=(), exclude=()):
    tmp = tempfile.TemporaryDirectory()
    logs = os.path.join(tmp.name, "logs")
    os.mkdir(logs)
    for n in ("access.log", "stream-access.log", "error.log"):
        shutil.copy(helpers.FIX / n, logs)
    db = os.path.join(tmp.name, "w.db")
    last = max(parse_access_line(l).ts for l in (helpers.FIX / "access.log").read_text().splitlines() if parse_access_line(l))
    live = LiveWindow(window=10, clock=lambda: last + 1)
    dm = DomainMap.load(str(helpers.FIX / "cache-domains"))
    hub = Hub()
    col = Collector(lambda: Ingestor(Storage(db), logs, dm, "+03:30", None, live=live), SystemSampler(cache_dir=tmp.name),
                    live, None, hub, exclude_ips=exclude)
    col.cycle(col.make_ingestor())
    srv = make_server("127.0.0.1", 0, hub, db, parse_allow("private"), frozenset(hide))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return tmp, srv, hub, "http://127.0.0.1:%d" % srv.server_address[1]


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.srv, cls.hub, cls.base = env(hide={"192.168.1.35"})

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def fetch(self, path):
        return urllib.request.urlopen(self.base + path, timeout=5)

    def test_pages_are_served_with_security_headers(self):
        for path, ctype in (("/", "text/html"), ("/static/app.js", "application/javascript"),
                            ("/static/lib.js", "application/javascript"), ("/static/style.css", "text/css")):
            with self.fetch(path) as r:
                self.assertEqual(r.status, 200, path)
                self.assertTrue(r.headers["Content-Type"].startswith(ctype), path)
                self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
                self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        with self.fetch("/") as r:
            html = r.read().decode()
        self.assertIn("Watch Cats", html)
        self.assertIn('dir="rtl"', html)
        for ref in ("/static/style.css", "/static/lib.js", "/static/app.js"):
            self.assertIn(ref, html)

    def test_only_whitelisted_files_are_served(self):
        for path in ("/static/../api.py", "/static/", "/static/index.html", "/..%2fapi.py", "/web/app.js"):
            with self.assertRaises(urllib.error.HTTPError, msg=path) as cm:
                self.fetch(path)
            self.assertEqual(cm.exception.code, 404, path)

    def test_summary_has_top_service_and_hides_the_server(self):
        s = json.loads(self.fetch("/api/summary?hours=8760").read())
        ips = [c["ip"] for c in s["clients"]]
        self.assertNotIn("192.168.1.35", ips)
        self.assertNotIn("192.168.1.35", [d["ip"] for d in s["devices"]])
        top = {c["ip"]: c["top_service"] for c in s["clients"]}
        self.assertEqual(top["192.168.1.152"], "PlayStation")
        self.assertEqual(top["192.168.1.101"], "Epic Games")


class ExcludeTests(unittest.TestCase):
    def test_excluded_ips_are_dropped_from_live_data(self):
        tmp, srv, hub, base = env(exclude={"192.168.1.101"})
        try:
            self.assertEqual(hub.snapshot["live"]["clients"], [])
            self.assertEqual(hub.snapshot["live"]["services"], [])
        finally:
            srv.shutdown()
            tmp.cleanup()


class LocalIpTests(unittest.TestCase):
    def test_parses_fib_trie(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "net"))
            with open(os.path.join(d, "net", "fib_trie"), "w") as f:
                f.write("Local:\n  +-- 0.0.0.0/0 3 0 5\n     |-- 192.168.1.35\n        /32 host LOCAL\n"
                        "     |-- 192.168.1.0\n        /24 link UNICAST\n     |-- 192.168.1.40\n        /32 host LOCAL\n"
                        "     |-- 192.168.1.255\n        /32 link BROADCAST\n")
            self.assertEqual(local_ips(d), {"127.0.0.1", "192.168.1.35", "192.168.1.40"})

    def test_missing_file_still_returns_loopback(self):
        self.assertEqual(local_ips("/nonexistent-proc"), {"127.0.0.1"})


if __name__ == "__main__":
    unittest.main()
