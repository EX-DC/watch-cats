"""Read-only JSON + Server-Sent-Events API (standard library only)."""
import ipaddress
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import __version__, presentation
from .storage import Storage

WEB = Path(__file__).resolve().parent / "web"
STATIC = {  # whitelist: nothing else is ever read from disk
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/style.css": ("style.css", "text/css; charset=utf-8"),
    "/static/lib.js": ("lib.js", "application/javascript; charset=utf-8"),
    "/static/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/static/fonts/Vazirmatn.woff2": ("fonts/Vazirmatn.woff2", "font/woff2"),  # optional, see `install-font`
}
FONT_FACE = ('@font-face{font-family:"Vazirmatn";src:url(/static/fonts/Vazirmatn.woff2) format("woff2");'
             'font-weight:100 900;font-display:swap}\n')


def style_css(web=WEB):
    """style.css, plus the @font-face rule only when the optional font file is installed."""
    css = (web / "style.css").read_text(encoding="utf-8")
    return (FONT_FACE if (web / "fonts" / "Vazirmatn.woff2").exists() else "") + css


CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"

LOGO_RE = re.compile(r"^([a-z0-9_]+)\.(svg|png|webp)$", re.I)  # file names may use capital letters
LOGO_TYPES = {"svg": "image/svg+xml", "png": "image/png", "webp": "image/webp"}
LOGO_CSP = "default-src 'none'; style-src 'unsafe-inline'; sandbox"  # an SVG opened directly cannot run scripts
_NEUTRAL_FILL = re.compile(r"fill\s*=\s*[\"'](none|currentcolor)[\"']")
_COLOUR_MARKERS = ("fill=", "fill:", "stroke=", "<lineargradient", "<radialgradient", "<image", "style=", "<style", "<rect")


def _svg_is_mono(path):
    """True for plain one-colour icons (Simple Icons style) that can be recoloured; False when the file
    carries its own colours or a background, which must be shown as they are."""
    try:
        if path.stat().st_size > 100_000:
            return False
        t = _NEUTRAL_FILL.sub("", path.read_text(encoding="utf-8", errors="ignore").lower())
    except OSError:
        return False
    return not any(m in t for m in _COLOUR_MARKERS)


def _logo_files(web=None):
    """{lower-case key: {"name": real file name, "ext": ext}}; svg wins over png over webp."""
    out, rank = {}, {"svg": 0, "png": 1, "webp": 2}
    try:
        names = sorted(os.listdir((web or WEB) / "logos"))
    except OSError:
        return out
    for n in names:
        m = LOGO_RE.match(n)
        if not m:
            continue
        key, ext = m[1].lower(), m[2].lower()
        if key not in out or rank[ext] < rank[out[key]["ext"]]:
            out[key] = {"name": n, "ext": ext}
    return out


def list_logos(web=None):
    """{service key: {"ext": ..., "mono": bool}} for the logo files found in web/logos."""
    web = web or WEB
    return {k: {"ext": v["ext"], "mono": v["ext"] == "svg" and _svg_is_mono(web / "logos" / v["name"])}
            for k, v in _logo_files(web).items()}


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


def summary(db_path, hours, hide=frozenset()):
    st = Storage(db_path, init=False)
    try:
        since = int(time.time()) - hours * 3600
        devices = [d for d in st.devices() if d["ip"] not in hide]
        kinds = {d["ip"]: d["kind"] for d in devices}
        agg = defaultdict(lambda: [0, 0, 0])
        top = defaultdict(lambda: defaultdict(int))
        for r in st.service_ip_totals(since):
            key = presentation.display_key(r["service"], kinds.get(r["ip"]))
            a = agg[key]
            a[0] += r["hit_bytes"]; a[1] += r["miss_bytes"]; a[2] += r["failed_requests"]
            top[r["ip"]][key] += r["hit_bytes"] + r["miss_bytes"]
        clients = []
        for c in st.clients(since):
            if c["ip"] in hide:
                continue
            best = max(top[c["ip"]], key=top[c["ip"]].get) if top[c["ip"]] else None
            clients.append(dict(c, top_service=presentation.name(best) if best else None, top_service_key=best))
        services = sorted(({"key": k, "name": presentation.name(k), "hit_bytes": v[0], "miss_bytes": v[1],
                            "failed_requests": v[2]} for k, v in agg.items()), key=lambda r: -(r["hit_bytes"] + r["miss_bytes"]))
        hit = sum(s["hit_bytes"] for s in services)
        miss = sum(s["miss_bytes"] for s in services)
        stream = [dict(s, name=presentation.name(s["service"])) for s in st.stream_totals(since)]
        return {"hours": hours, "hit_bytes": hit, "miss_bytes": miss,
                "hit_ratio": round(hit / (hit + miss), 3) if hit + miss else None,
                "services": services, "hourly": st.hourly(since), "clients": clients,
                "passthrough": stream, "errors": st.error_counts(since), "devices": devices}
    finally:
        st.close()


def make_server(host, port, hub, db_path, allow=None, hide_ips=frozenset()):
    class Handler(BaseHTTPRequestHandler):
        server_version = "WatchCats/" + __version__
        _head = False

        def do_HEAD(self):
            self._head = True
            self.do_GET()

        def log_message(self, *args):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not self._head:
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
                return self._json(summary(db_path, hours, hide_ips))
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
            if url.path == "/api/logos":
                return self._json({"logos": list_logos()})
            if url.path.startswith("/static/logos/"):
                return self._logo(url.path[len("/static/logos/"):])
            if url.path in STATIC:
                return self._static(*STATIC[url.path])
            return self._json({"error": "not found"}, 404)

        def _static(self, name, ctype):
            try:
                body = style_css().encode("utf-8") if name == "style.css" else (WEB / name).read_bytes()
            except OSError:
                return self._json({"error": "not found"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            if not self._head:
                self.wfile.write(body)

        def _logo(self, name):
            m = LOGO_RE.match(name)  # strict pattern: no slashes, no dots except the extension
            f = _logo_files().get(m[1].lower()) if m else None
            try:
                body = (WEB / "logos" / f["name"]).read_bytes() if f and f["ext"] == m[2].lower() else None
            except OSError:
                body = None
            if body is None:
                return self._json({"error": "not found"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", LOGO_TYPES[m[2].lower()])
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=3600")
            self.send_header("Content-Security-Policy", LOGO_CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if not self._head:
                self.wfile.write(body)

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            if self._head:
                return
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
