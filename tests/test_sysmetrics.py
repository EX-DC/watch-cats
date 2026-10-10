import os
import tempfile
import unittest

import helpers  # noqa: F401
from watchcats.live import LiveWindow
from watchcats.sysmetrics import DirSizer, SystemSampler


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


class SamplerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proc = os.path.join(self.tmp.name, "proc")
        self.sys = os.path.join(self.tmp.name, "sys")
        self.t = 0.0
        write(self.sys, "block/nvme0n1/x", "")
        write(self.sys, "block/loop0/x", "")
        write(self.sys, "class/net/enp0s31f6/speed", "1000\n")
        write(self.proc, "meminfo", "MemTotal:       16000000 kB\nMemFree: 1 kB\nMemAvailable:   12000000 kB\n")
        write(self.proc, "net/route",
              "Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\n"
              "enp0s31f6\t00000000\t0101A8C0\t0003\t0\t0\t100\n"
              "enp0s31f6\t0001A8C0\t00000000\t0001\t0\t0\t100\n")
        self.state(0, 100, 800, 0, 0, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def state(self, busy, tot_busy, idle, rx, tx, rd_sectors):
        write(self.proc, "stat", "cpu  %d 0 %d %d 0 0 0 0\ncpu0 1 0 1 1 0 0 0 0\ncpu1 1 0 1 1 0 0 0 0\n" % (busy, tot_busy - busy, idle))
        write(self.proc, "net/dev",
              "Inter-|   Receive |  Transmit\n face |bytes packets\n"
              "    lo: 999 1 0 0 0 0 0 0 999 1 0 0 0 0 0 0\n"
              "enp0s31f6: %d 1 0 0 0 0 0 0 %d 1 0 0 0 0 0 0\n" % (rx, tx))
        write(self.proc, "diskstats",
              "259 0 nvme0n1 1 0 %d 0 1 0 0 0 0 0 0 0\n259 3 nvme0n1p3 1 0 777777 0 1 0 0 0 0 0 0 0\n7 0 loop0 1 0 555555 0 1 0 0 0 0 0 0 0\n" % rd_sectors)

    def sampler(self):
        def clock():
            self.t += 1.0
            return self.t
        return SystemSampler(cache_dir=self.tmp.name, proc=self.proc, sysfs=self.sys, clock=clock)

    def test_rates(self):
        s = self.sampler()
        first = s.sample()
        self.assertEqual((first["cpu"]["pct"], first["net"]["rx_mbps"]), (0.0, 0.0))
        self.state(200, 200 + 0, 1600, 125_000_000, 62_500_000, 1_953_125)
        r = s.sample()
        self.assertEqual(r["net"]["iface"], "enp0s31f6")
        self.assertEqual((r["net"]["rx_mbps"], r["net"]["tx_mbps"], r["net"]["link_mbps"]), (1000.0, 500.0, 1000))
        self.assertEqual(r["disk"]["read_mb_s"], 1000.0)  # partition and loop device are not double counted
        self.assertEqual(r["cpu"]["cores"], 2)
        self.assertEqual(r["ram"]["used"], 4_000_000 * 1024)
        self.assertEqual(r["ram"]["pct"], 25.0)
        self.assertGreater(r["disk"]["total"], 0)

    def test_cpu_percent(self):
        s = self.sampler()
        s.sample()
        # stat line before: user 0, system 100, idle 800  -> total 900, idle 800
        # stat line after : user 100, system 1000, idle 1600 -> total 2700, idle 1600
        self.state(100, 1100, 1600, 0, 0, 0)
        r = s.sample()
        self.assertAlmostEqual(r["cpu"]["pct"], (1 - 800 / 1800) * 100, places=1)


class DirSizerTests(unittest.TestCase):
    def test_size(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "a/b.bin", "x" * 1000)
            write(d, "c.bin", "y" * 234)
            z = DirSizer(d)
            z.refresh()
            self.assertEqual(z._size, 1234)


class DirSizerUnreadableTests(unittest.TestCase):
    def test_missing_or_unreadable_gives_none_not_a_partial_number(self):
        z = DirSizer("/nonexistent-watchcats-dir")
        z.refresh()
        self.assertIsNone(z._size)
        self.assertGreaterEqual(z.unreadable, 1)


class LiveWindowTests(unittest.TestCase):
    def test_window(self):
        now = [1000.0]
        w = LiveWindow(window=10, clock=lambda: now[0])
        w.add(995, "steam", "1.1.1.1", "MISS", 12_500_000)
        w.add(999, "steam", "1.1.1.1", "HIT", 25_000_000)
        w.add(900, "steam", "1.1.1.1", "HIT", 99)  # too old, ignored
        w.add(999, "steam", "1.1.1.1", "NONE", 5)  # not a cache result
        t = w.totals()
        self.assertEqual(t[("steam", "1.1.1.1", "MISS")], 12_500_000)
        self.assertEqual(w.mbps(t[("steam", "1.1.1.1", "HIT")]), 20.0)
        now[0] = 1020.0  # everything slides out
        self.assertEqual(sum(w.totals().values()), 0)


if __name__ == "__main__":
    unittest.main()
