"""Live server metrics read straight from /proc and /sys (no dependencies)."""
import os
import threading
import time

_SKIP_BLOCK = ("loop", "ram", "zram", "dm-", "md", "sr")


class SystemSampler:
    """Call sample() about once a second; rates are computed against the previous call."""

    def __init__(self, cache_dir=None, proc="/proc", sysfs="/sys", clock=time.monotonic):
        self.cache_dir, self.proc, self.sysfs, self.clock = cache_dir, proc, sysfs, clock
        self._prev = None

    def _lines(self, *parts):
        with open(os.path.join(self.proc, *parts), encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()

    def _cpu(self):
        lines = self._lines("stat")
        vals = [int(x) for x in lines[0].split()[1:9]]
        cores = sum(1 for l in lines if l.startswith("cpu") and l[3:4].isdigit())
        return sum(vals), vals[3] + vals[4], cores  # total, idle+iowait, cores

    def _mem(self):
        info = {}
        for l in self._lines("meminfo"):
            k, _, v = l.partition(":")
            info[k] = int(v.split()[0]) * 1024
        total = info["MemTotal"]
        avail = info.get("MemAvailable", info.get("MemFree", 0))
        return total, total - avail

    def _iface(self):
        best = None
        try:
            for l in self._lines("net", "route")[1:]:
                p = l.split()
                if p[1] == "00000000" and (best is None or int(p[6]) < best[0]):
                    best = (int(p[6]), p[0])
        except (OSError, IndexError, ValueError):
            pass
        if best:
            return best[1]
        for l in self._lines("net", "dev")[2:]:
            name = l.split(":")[0].strip()
            if name != "lo":
                return name
        return None

    def _net(self, iface):
        for l in self._lines("net", "dev")[2:]:
            name, _, rest = l.partition(":")
            if name.strip() == iface:
                f = rest.split()
                return int(f[0]), int(f[8])  # rx_bytes, tx_bytes
        return 0, 0

    def _link(self, iface):
        try:
            with open(os.path.join(self.sysfs, "class", "net", iface, "speed")) as f:
                v = int(f.read().strip())
            return v if v > 0 else None
        except (OSError, ValueError, TypeError):
            return None

    def _disk_io(self):
        try:
            names = {n for n in os.listdir(os.path.join(self.sysfs, "block")) if not n.startswith(_SKIP_BLOCK)}
        except OSError:
            return 0, 0
        rd = wr = 0
        for l in self._lines("diskstats"):
            f = l.split()
            if len(f) > 9 and f[2] in names:
                rd += int(f[5]) * 512
                wr += int(f[9]) * 512
        return rd, wr

    def _fs(self):
        path = self.cache_dir if self.cache_dir and os.path.isdir(self.cache_dir) else "/"
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        avail = st.f_bavail * st.f_frsize
        pct = used / (used + avail) * 100 if used + avail else 0.0
        return {"path": path, "total": total, "used": used, "free": avail, "pct": round(pct, 1)}

    def sample(self):
        now = self.clock()
        cpu_total, cpu_idle, cores = self._cpu()
        mem_total, mem_used = self._mem()
        iface = self._iface()
        rx, tx = self._net(iface) if iface else (0, 0)
        rd, wr = self._disk_io()
        cur = (now, cpu_total, cpu_idle, rx, tx, rd, wr)
        prev, self._prev = self._prev, cur
        cpu_pct = rx_mbps = tx_mbps = rd_mb = wr_mb = 0.0
        if prev and now > prev[0]:
            dt = now - prev[0]
            dtot = cpu_total - prev[1]
            if dtot > 0:
                cpu_pct = (1 - (cpu_idle - prev[2]) / dtot) * 100
            rx_mbps = max(rx - prev[3], 0) * 8 / dt / 1e6
            tx_mbps = max(tx - prev[4], 0) * 8 / dt / 1e6
            rd_mb = max(rd - prev[5], 0) / dt / 1e6
            wr_mb = max(wr - prev[6], 0) / dt / 1e6
        return {
            "cpu": {"pct": round(cpu_pct, 1), "cores": cores},
            "ram": {"total": mem_total, "used": mem_used, "pct": round(mem_used / mem_total * 100, 1)},
            "net": {"iface": iface, "rx_mbps": round(rx_mbps, 1), "tx_mbps": round(tx_mbps, 1),
                    "link_mbps": self._link(iface) if iface else None},
            "disk": dict(self._fs(), read_mb_s=round(rd_mb, 1), write_mb_s=round(wr_mb, 1)),
        }


class DirSizer:
    """Total size of a directory tree, refreshed in the background (walking is slow)."""

    def __init__(self, path, ttl=60.0, clock=time.monotonic):
        self.path, self.ttl, self.clock = path, ttl, clock
        self._size, self._at, self._busy = None, None, False
        self.unreadable = 0

    def refresh(self):
        """A partial total would be misleading, so any unreadable entry makes the size None."""
        total, bad = 0, [0]

        def onerror(_e):
            bad[0] += 1

        for root, _dirs, files in os.walk(self.path, onerror=onerror):
            for name in files:
                try:
                    total += os.lstat(os.path.join(root, name)).st_size
                except OSError:
                    bad[0] += 1
        self._size = total if bad[0] == 0 else None
        self.unreadable = bad[0]
        self._at = self.clock()

    def _bg(self):
        try:
            self.refresh()
        finally:
            self._busy = False

    def get(self):
        if (self._at is None or self.clock() - self._at > self.ttl) and not self._busy:
            self._busy = True
            threading.Thread(target=self._bg, daemon=True).start()
        return self._size
