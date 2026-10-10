import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import helpers
from watchcats.api import is_allowed, make_server, parse_allow
from watchcats.domains import DomainMap
from watchcats.ingest import Ingestor
from watchcats.live import LiveWindow
from watchcats.parser import parse_access_line
from watchcats.runtime import Collector, Hub
from watchcats.storage import Storage
from watchcats.sysmetrics import SystemSampler


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        logs = os.path.join(cls.tmp.name, "logs")
        os.mkdir(logs)
        for n in ("access.log", "stream-access.log", "error.log"):
            shutil.copy(helpers.FIX / n, logs)
        cls.db = os.path.join(cls.tmp.name, "w.db")
        last = max(parse_access_line(l).ts for l in (helpers.FIX / "access.log").read_text().splitlines() if parse_access_line(l))
        live = LiveWindow(window=10, clock=lambda: last + 1)
        dm = DomainMap.load(str(helpers.FIX / "cache-domains"))
        cls.hub = Hub()
        cls.collector = Collector(lambda: Ingestor(Storage(cls.db), logs, dm, "+03:30", None, live=live),
                                  SystemSampler(cache_dir=cls.tmp.name), live, None, cls.hub)
        cls.collector.cycle(cls.collector.make_ingestor())
        cls.server = make_server("127.0.0.1", 0, cls.hub, cls.db, parse_allow("private"))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as r:
            return json.loads(r.read().decode())

    def test_version_and_health(self):
        self.assertRegex(self.get("/api/version")["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(self.get("/api/health")["ok"])

    def test_live_snapshot(self):
        snap = self.get("/api/live")
        for key in ("cpu", "ram", "net", "disk"):
            self.assertIn(key, snap["system"])
        svc = {s["key"]: s for s in snap["live"]["services"]}
        # only the last manifest request (Epic, 155157 bytes, HIT) is inside the 10 s window
        self.assertEqual(list(svc), ["epicgames"])
        self.assertEqual(svc["epicgames"]["serve_mbps"], round(155157 * 8 / 10 / 1e6, 1))
        self.assertEqual(svc["epicgames"]["serve_clients"], 1)
        self.assertEqual(snap["live"]["clients"][0]["ip"], "192.168.1.101")
        self.assertEqual(snap["live"]["clients"][0]["label"], "Windows")

    def test_summary(self):
        s = self.get("/api/summary?hours=8760")
        names = {x["name"]: x for x in s["services"]}
        self.assertEqual(names["PlayStation"]["hit_bytes"], 16777216)
        self.assertEqual(names["PlayStation"]["failed_requests"], 1)
        self.assertTrue(s["hourly"] and s["clients"] and s["devices"])
        self.assertTrue(any(e["kind"] == "upstream_timeout" for e in s["errors"]))
        self.assertEqual(self.get("/api/summary?hours=1")["services"], [])

    def test_errors_endpoint(self):
        e = self.get("/api/errors?kind=upstream_403")
        self.assertEqual(e["items"][0]["host"], "gs2.ww.prod.dl.playstation.net")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/api/errors")
        self.assertEqual(cm.exception.code, 400)

    def test_not_found_and_bad_input(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/nope")
        self.assertEqual(cm.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/api/summary?hours=abc")
        self.assertEqual(cm.exception.code, 400)

    def test_stream_sends_snapshot(self):
        with urllib.request.urlopen(self.base + "/api/stream", timeout=5) as r:
            self.assertEqual(r.headers["Content-Type"], "text/event-stream")
            line = r.readline().decode()
            while line.strip() == "":
                line = r.readline().decode()
            self.assertTrue(line.startswith("data: "))
            self.assertIn("system", json.loads(line[6:]))


class AllowTests(unittest.TestCase):
    def test_private_default(self):
        a = parse_allow("private")
        for ip in ("192.168.1.150", "10.1.2.3", "172.20.0.5", "127.0.0.1", "::ffff:192.168.1.7"):
            self.assertTrue(is_allowed(ip, a), ip)
        for ip in ("8.8.8.8", "172.32.0.1", "93.184.216.34"):
            self.assertFalse(is_allowed(ip, a), ip)

    def test_custom_and_any(self):
        self.assertTrue(is_allowed("192.168.1.9", parse_allow("192.168.1.0/24")))
        self.assertFalse(is_allowed("192.168.2.9", parse_allow("192.168.1.0/24")))
        self.assertTrue(is_allowed("8.8.8.8", parse_allow("any")))


if __name__ == "__main__":
    unittest.main()
