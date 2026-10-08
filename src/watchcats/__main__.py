import argparse
import os
import sys
import time

from . import __version__, presentation
from .domains import DomainMap
from .ingest import Ingestor
from .storage import Storage


def _mb(n):
    return "%.1f MB" % ((n or 0) / 1e6)


def cmd_ingest(a):
    domains = DomainMap.load(a.domains) if a.domains else DomainMap()
    st = Storage(a.db)
    ing = Ingestor(st, a.log_dir, domains, a.tz, a.dns_log)
    while True:
        stats = ing.poll()
        print("ingested:", {k: "%d lines, %d parsed" % v for k, v in stats.items()})
        if a.once:
            return 0
        time.sleep(a.interval)


def cmd_report(a):
    st = Storage(a.db)
    since = int(time.time()) - a.hours * 3600
    kinds = {d["ip"]: d["kind"] for d in st.devices()}
    print("== Services (last %dh) ==" % a.hours)
    for r in st.service_totals(since):
        tot = r["hit_bytes"] + r["miss_bytes"]
        ratio = "%d%%" % (100 * r["hit_bytes"] / tot) if tot else "-"
        print("%-18s HIT %-10s MISS %-10s hit-ratio %-5s failed-requests %d" % (
            presentation.name(r["service"]), _mb(r["hit_bytes"]), _mb(r["miss_bytes"]), ratio, r["failed_requests"]))
    print("\n== Clients (auto-detected) ==")
    for c in st.clients(since):
        print("%-15s %-9s HIT %-10s MISS %s" % (c["ip"], c["label"], _mb(c["hit_bytes"]), _mb(c["miss_bytes"])))
    print("\n== HTTPS pass-through (not cached) ==")
    for s in st.stream_totals(since)[:10]:
        print("%-12s %-40s %4d sessions %s" % (presentation.name(s["service"]), s["host"], s["sessions"], _mb(s["bytes"])))
    print("\n== Errors ==")
    for e in st.error_counts(since)[:10]:
        print("%-18s %-45s x%d" % (e["kind"], e["host"], e["count"]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="watchcats", description="Watch Cats %s" % __version__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest", help="read LanCache logs into the database")
    i.add_argument("--log-dir", required=True, help="folder containing access.log, stream-access.log, error.log")
    i.add_argument("--db", default="watchcats.db")
    i.add_argument("--domains", help="folder with cache_domains.json (copy of /opt/cache-domains)")
    i.add_argument("--dns-log", help="optional BIND default.log")
    i.add_argument("--tz", default="local", help="timezone of error logs: local, +03:30, UTC")
    i.add_argument("--once", action="store_true")
    i.add_argument("--interval", type=float, default=1.0)
    i.set_defaults(fn=cmd_ingest)
    r = sub.add_parser("report", help="print a summary from the database")
    r.add_argument("--db", default="watchcats.db")
    r.add_argument("--hours", type=int, default=24 * 365, help="how far back to look (default: everything)")
    r.set_defaults(fn=cmd_report)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
