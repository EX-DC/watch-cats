"""Read-only JSON + Server-Sent-Events API (standard library only)."""
import ipaddress
import json
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__, presentation
from .storage import Storage

PRIVATE_NETS = [ipaddress.ip_network(n) for n in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1/128", "fe80::/10", "fc00::/7")]


def parse_allow(text):
    """'private' (default), 'any', or comma separated CIDRs like 192.168.1.0/24."""
    t = (text or "private").strip().lower()
    if t == "any":
        return None
    if t == "private":
        return PRIVATE_NETS
    return [ipaddress.ip_network(x.strip(), strict=False) for x in t.split(",") if x.strip()]


def is_allowed(addr, allow):
    if allow is None:
        return True
    ip = ipaddress.ip_address(addr)
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return any(ip in n for n in allow)


def summary(db_path, hours):
    st = Storage(db_path, init=False)
    try:
        since = int(time.time()) - hours * 3600
        devices = st.devices()
        kinds = {d["ip"]: d["kind"] for d in devices}
        agg = defaultdict(lambda: [0, 0, 0])
        for r in st.service_ip_totals(since):
            a = agg[presentation.display_key(r["service"], kinds.get(r["ip"]))]
            a[0] += r["hit_bytes"]; a[1] += r["miss_bytes"]; a[2] += r["failed_requests"]
        services = sorted(({"key": k, "name": presentation.name(k), "hit_bytes": v[0], "miss_bytes": v[1],
                            "failed_requests": v[2]} for k, v in agg.items()), key=lambda r: -(r["hit_bytes"] + r["miss_bytes"]))
        hit = sum(s["hit_bytes"] for s in services)
        miss = sum(s["miss_bytes"] for s in services)
        stream = [dict(s, name=presentation.name(s["service"])) for s in st.stream_totals(since)]
        return {"hours": hours, "hit_bytes": hit, "miss_bytes": miss,
                "hit_ratio": round(hit / (hit + miss), 3) if hit + miss else None,
                "services": services, "hourly": st.hourly(since), "clients": st.clients(since),
                "passthrough": stream, "errors": st.error_counts(since), "devices": devices}
    finally:
        st.close()


def make_server(host, port, hub, db_path, allow=None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "WatchCats/" + __version__

        def log_message(self, *args):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not is_allowed(self.client_address[0], allow):
                return self._json({"error": "forbidden"}, 403)
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path == "/api/version":
                return self._json({"version": __version__})
            if url.path == "/api/health":
                return self._json({"ok": hub.snapshot is not None, "seq": hub.seq})
            if url.path == "/api/live":
                return self._json(hub.snapshot, 200) if hub.snapshot else self._json({"error": "starting"}, 503)
            if url.path == "/api/summary":
                try:
                    hours = min(max(int(q.get("hours", ["24"])[0]), 1), 8760)
                except ValueError:
                    return self._json({"error": "bad hours"}, 400)
                return self._json(summary(db_path, hours))
            if url.path == "/api/errors":
                kind = q.get("kind", [""])[0]
                if not kind:
                    return self._json({"error": "kind is required"}, 400)
                limit = min(max(int(q.get("limit", ["20"])[0]), 1), 200)
                st = Storage(db_path, init=False)
                try:
                    return self._json({"kind": kind, "items": st.recent_errors(kind, limit)})
                finally:
                    st.close()
            if url.path == "/api/stream":
                return self._stream()
            return self._json({"error": "not found"}, 404)

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            seq = 0
            try:
                while True:
                    seq, snap = hub.wait_next(seq, 15.0)
                    msg = ": keepalive\n\n" if snap is None else "data: %s\n\n" % json.dumps(snap, ensure_ascii=False)
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
