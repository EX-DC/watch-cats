"""SQLite storage (standard library only). One writer, many readers (WAL mode)."""
import sqlite3

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS offsets(path TEXT PRIMARY KEY, inode INTEGER, offset INTEGER);
CREATE TABLE IF NOT EXISTS traffic(
  minute INTEGER, service TEXT, ip TEXT, cache TEXT, ok INTEGER, requests INTEGER, bytes INTEGER,
  PRIMARY KEY(minute, service, ip, cache, ok));
CREATE TABLE IF NOT EXISTS stream(
  minute INTEGER, service TEXT, ip TEXT, host TEXT, sessions INTEGER, bytes INTEGER,
  PRIMARY KEY(minute, service, ip, host));
CREATE TABLE IF NOT EXISTS devices(
  ip TEXT PRIMARY KEY, kind TEXT, label TEXT, confidence REAL, first_seen INTEGER, last_seen INTEGER);
CREATE TABLE IF NOT EXISTS errors(ts INTEGER, kind TEXT, ip TEXT, host TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS errors_ts ON errors(ts);
"""


class Storage:
    def __init__(self, path, init=True):
        """init=False: open an existing database for reading (no schema work)."""
        self.conn = sqlite3.connect(path)
        if init:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SCHEMA)
            with self.conn:
                self.conn.execute("INSERT OR IGNORE INTO meta VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))

    def close(self):
        self.conn.close()

    # --- offsets -------------------------------------------------------
    def get_offset(self, path):
        row = self.conn.execute("SELECT inode, offset FROM offsets WHERE path=?", (path,)).fetchone()
        return row if row else (None, 0)

    def set_offset(self, path, inode, offset):
        self.conn.execute("INSERT OR REPLACE INTO offsets VALUES(?,?,?)", (path, inode, offset))

    # --- writes (call inside `with storage.conn:`) ------------------------
    def add_traffic(self, rows):
        self.conn.executemany(
            "INSERT INTO traffic VALUES(?,?,?,?,?,?,?) ON CONFLICT(minute,service,ip,cache,ok) DO UPDATE "
            "SET requests=requests+excluded.requests, bytes=bytes+excluded.bytes", rows)

    def add_stream(self, rows):
        self.conn.executemany(
            "INSERT INTO stream VALUES(?,?,?,?,?,?) ON CONFLICT(minute,service,ip,host) DO UPDATE "
            "SET sessions=sessions+excluded.sessions, bytes=bytes+excluded.bytes", rows)

    def add_errors(self, rows):
        self.conn.executemany("INSERT INTO errors VALUES(?,?,?,?,?)", rows)

    def touch_devices(self, rows):
        """rows: (ip, kind, label, confidence, ts). A more confident signal wins."""
        self.conn.executemany(
            "INSERT INTO devices VALUES(?,?,?,?,?,?) ON CONFLICT(ip) DO UPDATE SET "
            "kind=CASE WHEN excluded.confidence>=devices.confidence THEN excluded.kind ELSE devices.kind END,"
            "label=CASE WHEN excluded.confidence>=devices.confidence THEN excluded.label ELSE devices.label END,"
            "confidence=MAX(excluded.confidence,devices.confidence),"
            "first_seen=MIN(devices.first_seen,excluded.first_seen),"
            "last_seen=MAX(devices.last_seen,excluded.last_seen)",
            [(ip, k, lab, c, ts, ts) for ip, k, lab, c, ts in rows])

    def purge(self, before_ts):
        with self.conn:
            for table, col in (("traffic", "minute"), ("stream", "minute"), ("errors", "ts")):
                self.conn.execute("DELETE FROM %s WHERE %s<?" % (table, col), (before_ts,))

    # --- reads ---------------------------------------------------------
    def service_totals(self, since):
        q = ("SELECT service,"
             "SUM(CASE WHEN cache='HIT' AND ok=1 THEN bytes ELSE 0 END) AS hb,"
             "SUM(CASE WHEN cache='MISS' AND ok=1 THEN bytes ELSE 0 END) AS mb,"
             "SUM(CASE WHEN cache='HIT' AND ok=1 THEN requests ELSE 0 END),"
             "SUM(CASE WHEN cache='MISS' AND ok=1 THEN requests ELSE 0 END),"
             "SUM(CASE WHEN ok=0 THEN requests ELSE 0 END) "
             "FROM traffic WHERE minute>=? GROUP BY service ORDER BY hb+mb DESC")
        return [dict(zip(("service", "hit_bytes", "miss_bytes", "hit_requests", "miss_requests", "failed_requests"), r))
                for r in self.conn.execute(q, (since,))]

    def service_ip_totals(self, since):
        q = ("SELECT service, ip,"
             "SUM(CASE WHEN cache='HIT' AND ok=1 THEN bytes ELSE 0 END),"
             "SUM(CASE WHEN cache='MISS' AND ok=1 THEN bytes ELSE 0 END),"
             "SUM(CASE WHEN ok=0 THEN requests ELSE 0 END) "
             "FROM traffic WHERE minute>=? GROUP BY service, ip")
        return [dict(zip(("service", "ip", "hit_bytes", "miss_bytes", "failed_requests"), r))
                for r in self.conn.execute(q, (since,))]

    def hourly(self, since):
        q = ("SELECT minute/3600*3600,"
             "SUM(CASE WHEN cache='HIT' AND ok=1 THEN bytes ELSE 0 END),"
             "SUM(CASE WHEN cache='MISS' AND ok=1 THEN bytes ELSE 0 END) "
             "FROM traffic WHERE minute>=? GROUP BY 1 ORDER BY 1")
        return [{"hour": h, "hit_bytes": a, "miss_bytes": b} for h, a, b in self.conn.execute(q, (since,))]

    def clients(self, since):
        q = ("SELECT t.ip, COALESCE(d.kind,'unknown'), COALESCE(d.label,'Unknown'), "
             "SUM(CASE WHEN t.cache='HIT' AND t.ok=1 THEN t.bytes ELSE 0 END) AS hb,"
             "SUM(CASE WHEN t.cache='MISS' AND t.ok=1 THEN t.bytes ELSE 0 END) AS mb, MAX(t.minute) "
             "FROM traffic t LEFT JOIN devices d ON d.ip=t.ip WHERE t.minute>=? GROUP BY t.ip ORDER BY hb+mb DESC")
        return [dict(zip(("ip", "kind", "label", "hit_bytes", "miss_bytes", "last_seen"), r))
                for r in self.conn.execute(q, (since,))]

    def stream_totals(self, since):
        q = ("SELECT service, host, SUM(sessions), SUM(bytes) FROM stream WHERE minute>=? "
             "GROUP BY service, host ORDER BY 4 DESC")
        return [dict(zip(("service", "host", "sessions", "bytes"), r)) for r in self.conn.execute(q, (since,))]

    def error_counts(self, since):
        q = "SELECT kind, host, COUNT(*), MAX(ts) FROM errors WHERE ts>=? GROUP BY kind, host ORDER BY 3 DESC"
        return [dict(zip(("kind", "host", "count", "last"), r)) for r in self.conn.execute(q, (since,))]

    def recent_errors(self, kind, limit=20):
        q = "SELECT ts, ip, host, detail FROM errors WHERE kind=? ORDER BY ts DESC LIMIT ?"
        return [dict(zip(("ts", "ip", "host", "detail"), r)) for r in self.conn.execute(q, (kind, limit))]

    def devices(self):
        q = "SELECT ip, kind, label, confidence, first_seen, last_seen FROM devices ORDER BY last_seen DESC"
        return [dict(zip(("ip", "kind", "label", "confidence", "first_seen", "last_seen"), r))
                for r in self.conn.execute(q)]
