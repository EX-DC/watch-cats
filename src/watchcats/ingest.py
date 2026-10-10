"""Reads new log lines, aggregates them per minute and stores them atomically."""
import os
from collections import defaultdict

from . import devices as dev
from .domains import DomainMap
from .parser import (parse_access_line, parse_error_line, parse_named_line, parse_stream_line, parse_tz)
from .tailer import Tailer


class Ingestor:
    def __init__(self, storage, log_dir, domains=None, tz="local", dns_log=None, live=None):
        self.storage = storage
        self.live = live
        self.domains = domains or DomainMap()
        self.tz = parse_tz(tz) if isinstance(tz, str) else tz
        paths = {"access": os.path.join(log_dir, "access.log"),
                 "stream": os.path.join(log_dir, "stream-access.log"),
                 "error": os.path.join(log_dir, "error.log")}
        if dns_log:
            paths["dns"] = dns_log
        self.tailers = {}
        for key, path in paths.items():
            inode, offset = storage.get_offset(path)
            self.tailers[key] = Tailer(path, inode, offset)

    def poll(self):
        """Process everything new. Returns {source: (lines, parsed)}."""
        stats, traffic, stream, errors, devs = {}, defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), [], {}
        for key, tailer in self.tailers.items():
            lines = tailer.read_new()
            parsed = 0
            for line in lines:
                if key == "access":
                    e = parse_access_line(line)
                    if not e:
                        continue
                    parsed += 1
                    ok = 1 if e.status < 400 else 0
                    cell = traffic[(e.ts // 60 * 60, e.service, e.ip, e.cache, ok)]
                    cell[0] += 1
                    cell[1] += e.bytes
                    if self.live is not None and ok:
                        self.live.add(e.ts, e.service, e.ip, e.cache, e.bytes)
                    found = dev.detect(e.ua)
                    cand = (found[0], found[1], found[2]) if found else ("unknown", "Unknown", 0.0)
                    old = devs.get(e.ip)
                    if old is None or cand[2] > old[2]:
                        devs[e.ip] = (cand[0], cand[1], cand[2], e.ts)
                elif key == "stream":
                    s = parse_stream_line(line)
                    if not s:
                        continue
                    parsed += 1
                    svc = self.domains.lookup(s.host) or "other"
                    cell = stream[(s.ts // 60 * 60, svc, s.ip, s.host)]
                    cell[0] += 1
                    cell[1] += s.bytes_sent
                    devs.setdefault(s.ip, ("unknown", "Unknown", 0.0, s.ts))
                else:
                    e = parse_named_line(line, self.tz) if key == "dns" else parse_error_line(line, self.tz)
                    if e:
                        parsed += 1
                        errors.append((e.ts, e.kind, e.ip, e.host, e.detail))
            stats[key] = (len(lines), parsed)
        with self.storage.conn:  # data and offsets commit together
            self.storage.add_traffic([k + tuple(v) for k, v in traffic.items()])
            self.storage.add_stream([k + tuple(v) for k, v in stream.items()])
            self.storage.add_errors(errors)
            self.storage.touch_devices([(ip, k, lab, c, ts) for ip, (k, lab, c, ts) in devs.items()])
            for key, tailer in self.tailers.items():
                self.storage.set_offset(tailer.path, tailer.inode, tailer.offset)
        return stats
