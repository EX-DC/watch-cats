import os
import shutil
import tempfile
import unittest

import helpers
from watchcats.domains import DomainMap
from watchcats.ingest import Ingestor
from watchcats.storage import Storage


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = os.path.join(self.tmp.name, "logs")
        os.mkdir(self.logs)
        for n in ("access.log", "stream-access.log", "error.log"):
            shutil.copy(helpers.FIX / n, self.logs)
        self.dns = os.path.join(self.tmp.name, "named.log")
        shutil.copy(helpers.FIX / "named-default.log", self.dns)
        self.db = os.path.join(self.tmp.name, "w.db")
        self.dm = DomainMap.load(str(helpers.FIX / "cache-domains"))

    def tearDown(self):
        self.tmp.cleanup()

    def make(self):
        return Ingestor(Storage(self.db), self.logs, self.dm, "+03:30", self.dns)

    def test_end_to_end(self):
        ing = self.make()
        stats = ing.poll()
        self.assertEqual(stats["access"], (11, 9))  # health line and garbage are skipped
        st = ing.storage
        totals = {r["service"]: r for r in st.service_totals(0)}
        self.assertEqual(totals["sony"]["hit_bytes"], 16777216)
        self.assertEqual(totals["sony"]["miss_bytes"], 7864320)  # the 403 is not counted as traffic
        self.assertEqual(totals["sony"]["failed_requests"], 1)
        self.assertEqual(totals["steam"]["hit_bytes"], 203152)
        self.assertEqual(totals["epicgames"]["miss_bytes"], 909617)
        self.assertEqual(totals["epicgames"]["hit_bytes"], 909617 + 155157)
        self.assertEqual(totals["epicgames"]["failed_requests"], 1)  # the 504
        kinds = {d["ip"]: d["kind"] for d in st.devices()}
        self.assertEqual(kinds["192.168.1.152"], "ps5")
        self.assertEqual(kinds["192.168.1.101"], "windows")
        self.assertEqual(kinds["192.168.1.150"], "windows")  # Epic UA (0.8) beats Steam UA (0.4)
        self.assertEqual(kinds["192.168.1.35"], "tool")
        streams = {(r["service"], r["host"]): r for r in st.stream_totals(0)}
        self.assertEqual(streams[("epicgames", "egdownload.fastly-edge.com")]["bytes"], 98745337 + 1587802370)
        self.assertEqual(streams[("epicgames", "egdownload.fastly-edge.com")]["sessions"], 2)
        self.assertIn(("wsus", "geo.prod.do.dsp.mp.microsoft.com"), streams)
        self.assertIn(("other", "unknown.example.org"), streams)
        errs = {(e["kind"], e["host"]): e["count"] for e in st.error_counts(0)}
        self.assertEqual(errs[("upstream_timeout", "egs-cloudfront-chunks.epicgamescdn.com")], 1)
        self.assertEqual(errs[("upstream_403", "gs2.ww.prod.dl.playstation.net")], 1)
        self.assertEqual(errs[("dns_unresolved", "ctldl.windowsupdate.com")], 1)
        self.assertEqual(errs[("dns_timed_out", "fuk01.ps5.update.playstation.net")], 1)
        self.assertTrue(st.hourly(0))
        self.assertEqual(st.clients(0)[0]["ip"], "192.168.1.152")  # biggest by bytes

    def test_second_poll_adds_nothing_and_restart_resumes(self):
        ing = self.make()
        ing.poll()
        before = ing.storage.service_totals(0)
        self.assertEqual(ing.poll()["access"], (0, 0))
        ing.storage.close()
        ing2 = self.make()  # simulates a restart: offsets come from the database
        self.assertEqual(ing2.poll()["access"], (0, 0))
        self.assertEqual(ing2.storage.service_totals(0), before)

    def test_appended_lines_are_added(self):
        ing = self.make()
        ing.poll()
        with open(os.path.join(self.logs, "access.log"), "a") as f:
            f.write('[steam] 192.168.1.150 / - - - [03/Oct/2026:15:26:00 +0330] "GET /depot/1/chunk/a HTTP/1.1" 200 1000 "-" "Valve/Steam HTTP Client 1.0" "HIT" "h" "-"\n')
        self.assertEqual(ing.poll()["access"], (1, 1))
        steam = {r["service"]: r for r in ing.storage.service_totals(0)}["steam"]
        self.assertEqual(steam["hit_bytes"], 203152 + 1000)

    def test_purge(self):
        ing = self.make()
        ing.poll()
        ing.storage.purge(2 ** 40)
        self.assertEqual(ing.storage.service_totals(0), [])


if __name__ == "__main__":
    unittest.main()
