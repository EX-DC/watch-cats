"""Collector (1 s loop) and Hub (latest snapshot + wake-up for streaming clients)."""
import logging
import threading
import time
from collections import defaultdict

from . import __version__, presentation

log = logging.getLogger("watchcats")


class Hub:
    def __init__(self):
        self._cond = threading.Condition()
        self.seq = 0
        self.snapshot = None

    def publish(self, snap):
        with self._cond:
            self.seq += 1
            self.snapshot = snap
            self._cond.notify_all()

    def wait_next(self, last_seq, timeout=15.0):
        with self._cond:
            self._cond.wait_for(lambda: self.seq != last_seq, timeout)
            return self.seq, self.snapshot


class Collector:
    def __init__(self, make_ingestor, sampler, live, sizer, hub, interval=1.0, retention_days=30):
        self.make_ingestor, self.sampler, self.live, self.sizer = make_ingestor, sampler, live, sizer
        self.hub, self.interval, self.retention_days = hub, interval, retention_days
        self.errors = 0
        self._last_purge = 0.0

    def build(self, storage):
        kinds = {d["ip"]: (d["kind"], d["label"]) for d in storage.devices()}
        svc = defaultdict(lambda: {"fill": 0, "serve": 0, "sc": set(), "fc": set()})
        cli = defaultdict(lambda: {"fill": 0, "serve": 0, "svcs": set()})
        for (service, ip, cache), nbytes in self.live.totals().items():
            key = presentation.display_key(service, kinds.get(ip, ("unknown", ""))[0])
            s, c = svc[key], cli[ip]
            c["svcs"].add(presentation.name(key))
            if cache == "HIT":
                s["serve"] += nbytes; c["serve"] += nbytes; s["sc"].add(ip)
            else:
                s["fill"] += nbytes; c["fill"] += nbytes; s["fc"].add(ip)
        m = self.live.mbps
        services = sorted(({"key": k, "name": presentation.name(k), "serve_mbps": m(v["serve"]),
                            "fill_mbps": m(v["fill"]), "serve_clients": len(v["sc"]), "fill_clients": len(v["fc"])}
                           for k, v in svc.items()), key=lambda r: -(r["serve_mbps"] + r["fill_mbps"]))
        clients = sorted(({"ip": ip, "kind": kinds.get(ip, ("unknown", "Unknown"))[0],
                           "label": kinds.get(ip, ("unknown", "Unknown"))[1], "serve_mbps": m(v["serve"]),
                           "fill_mbps": m(v["fill"]), "services": sorted(v["svcs"])} for ip, v in cli.items()),
                         key=lambda r: -(r["serve_mbps"] + r["fill_mbps"]))
        system = self.sampler.sample()
        system["disk"]["cache_bytes"] = self.sizer.get() if self.sizer else None
        system["disk"]["cache_unreadable"] = self.sizer.unreadable if self.sizer else 0
        return {"ts": int(time.time()), "version": __version__, "window_s": self.live.window,
                "system": system, "collector_errors": self.errors,
                "live": {"serve_mbps": system["net"]["tx_mbps"], "fill_mbps": system["net"]["rx_mbps"],
                         "serving_clients": sum(1 for c in clients if c["serve_mbps"] > 0),
                         "services": services, "clients": clients}}

    def cycle(self, ingestor):
        ingestor.poll()
        self.hub.publish(self.build(ingestor.storage))
        if time.time() - self._last_purge > 3600:
            ingestor.storage.purge(int(time.time()) - self.retention_days * 86400)
            self._last_purge = time.time()

    def run(self, stop=None):
        stop = stop or threading.Event()
        ingestor = self.make_ingestor()  # created here: SQLite connections belong to one thread
        while not stop.is_set():
            t0 = time.monotonic()
            try:
                self.cycle(ingestor)
            except Exception:
                self.errors += 1
                log.exception("collector cycle failed")
            stop.wait(max(0.0, self.interval - (time.monotonic() - t0)))
