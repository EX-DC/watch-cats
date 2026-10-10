"""Sliding window of recent cache traffic, used for live per-service / per-client speeds.

Speeds are estimates: nginx logs a request when it *finishes*, so the numbers are
smoothed over the window (default 10 s) and are not instantaneous throughput.
"""
import time
from collections import Counter, defaultdict


class LiveWindow:
    def __init__(self, window=10, clock=time.time):
        self.window, self.clock = window, clock
        self._b = defaultdict(Counter)  # second -> {(service, ip, cache): bytes}

    def add(self, ts, service, ip, cache, nbytes):
        if ts >= self.clock() - self.window and cache in ("HIT", "MISS"):
            self._b[int(ts)][(service, ip, cache)] += nbytes

    def totals(self):
        """{(service, ip, cache): bytes} for the last `window` seconds."""
        cutoff = self.clock() - self.window
        for s in [s for s in self._b if s < cutoff]:
            del self._b[s]
        out = Counter()
        for c in self._b.values():
            out.update(c)
        return out

    def mbps(self, nbytes):
        return round(nbytes * 8 / self.window / 1e6, 1)
