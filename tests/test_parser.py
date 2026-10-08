import unittest
from datetime import datetime, timezone

import helpers
from watchcats.parser import (parse_access_line, parse_error_line, parse_named_line, parse_stream_line, parse_tz)

LINES = (helpers.FIX / "access.log").read_text().splitlines()
TZ = parse_tz("+03:30")


class ParserTests(unittest.TestCase):
    def test_access_line(self):
        e = parse_access_line(LINES[3])
        self.assertEqual((e.service, e.ip, e.status, e.bytes, e.cache), ("sony", "192.168.1.152", 206, 7864320, "MISS"))
        self.assertEqual(e.host, "gs2.ww.prod.dl.playstation.net")
        self.assertIn("PlayStation 5", e.ua)
        want = datetime(2026, 10, 3, 22, 58, 9, tzinfo=TZ)
        self.assertEqual(e.ts, int(want.timestamp()))

    def test_health_check_and_garbage_are_ignored(self):
        self.assertIsNone(parse_access_line(LINES[0]))
        self.assertIsNone(parse_access_line(LINES[-1]))

    def test_cache_dash_is_none(self):
        line = LINES[1].replace('"MISS"', '"-"')
        self.assertEqual(parse_access_line(line).cache, "NONE")

    def test_stream_line(self):
        s = parse_stream_line("192.168.1.101 [04/Oct/2026:23:29:35 +0330] TCP 200 EgDownload.fastly-edge.com 1587802370 274543 28.023")
        self.assertEqual((s.ip, s.host, s.bytes_sent), ("192.168.1.101", "egdownload.fastly-edge.com", 1587802370))

    def test_error_kinds_and_no_paths_kept(self):
        lines = (helpers.FIX / "error.log").read_text().splitlines()
        e = [parse_error_line(l, TZ) for l in lines]
        self.assertEqual([x.kind if x else None for x in e],
                         ["dns_unresolved", "upstream_403", "upstream_timeout", None])
        self.assertEqual(e[1].ip, "192.168.1.152")
        self.assertEqual(e[1].host, "gs2.ww.prod.dl.playstation.net")
        for x in e[:3]:
            self.assertNotIn("/", x.detail.replace("(110: Connection timed out)", ""))
            self.assertNotIn("?", x.detail)
        self.assertEqual(e[2].ts, int(datetime(2026, 10, 4, 17, 14, 43, tzinfo=TZ).timestamp()))

    def test_named_line(self):
        lines = (helpers.FIX / "named-default.log").read_text().splitlines()
        self.assertIsNone(parse_named_line(lines[0], TZ))
        e = parse_named_line(lines[1], TZ)
        self.assertEqual((e.kind, e.ip, e.host), ("dns_timed_out", "192.168.1.152", "fuk01.ps5.update.playstation.net"))

    def test_tz(self):
        self.assertEqual(parse_tz("UTC"), timezone.utc)
        with self.assertRaises(ValueError):
            parse_tz("tehran")


if __name__ == "__main__":
    unittest.main()
