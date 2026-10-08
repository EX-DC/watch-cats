"""Parsers for the LanCache (nginx) and BIND log formats seen in production."""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

ACCESS_RE = re.compile(
    r'^\[(?P<tag>[^\]]+)\] (?P<ip>\S+) / - - - \[(?P<ts>[^\]]+)\] "(?P<req>[^"]*)" '
    r'(?P<status>\d{3}) (?P<bytes>\d+) "[^"]*" "(?P<ua>[^"]*)" "(?P<cache>[^"]*)" '
    r'"(?P<host>[^"]*)" "[^"]*"\s*$')
STREAM_RE = re.compile(
    r'^(?P<ip>\S+) \[(?P<ts>[^\]]+)\] (?P<proto>\S+) (?P<status>\d{3}) (?P<host>\S+) '
    r'(?P<sent>\d+) (?P<recv>\d+) (?P<dur>[\d.]+)\s*$')
ERROR_RE = re.compile(
    r'^(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) \[(?P<level>\w+)\] \d+#\d+: (?:\*\d+ )?(?P<msg>.*)$')
NAMED_RE = re.compile(
    r'^(?P<ts>\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}:\d{2})\.\d+ client @\S+ (?P<ip>[\d.]+)#\d+ '
    r'\((?P<q>[^)]*)\): query failed \((?P<why>[^)]*)\) for (?P<name>\S+?)/IN/(?P<rr>\w+)')
_IPV4 = re.compile(r'^\d{1,3}(\.\d{1,3}){3}$')


@dataclass(frozen=True)
class AccessEntry:
    service: str
    ip: str
    ts: int
    method: str
    status: int
    bytes: int
    ua: str
    cache: str  # HIT / MISS / NONE
    host: str


@dataclass(frozen=True)
class StreamEntry:
    ip: str
    ts: int
    status: int
    host: str
    bytes_sent: int
    bytes_recv: int
    duration: float


@dataclass(frozen=True)
class ErrorEntry:
    ts: int
    kind: str
    ip: str
    host: str
    detail: str


def parse_tz(text):
    """'local', '+03:30', '-0500' or 'UTC' -> tzinfo."""
    t = (text or "local").strip()
    if t.lower() == "local":
        return datetime.now().astimezone().tzinfo
    if t.upper() in ("UTC", "Z"):
        return timezone.utc
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", t)
    if not m:
        raise ValueError("bad timezone: %r" % text)
    delta = timedelta(hours=int(m[2]), minutes=int(m[3]))
    return timezone(delta if m[1] == "+" else -delta)


def _access_ts(s):
    m = re.fullmatch(r"(\d{2})/(\w{3})/(\d{4}):(\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})", s)
    if not m or m[2] not in _MONTHS:
        raise ValueError(s)
    off = timedelta(hours=int(m[8]), minutes=int(m[9]))
    tz = timezone(off if m[7] == "+" else -off)
    return int(datetime(int(m[3]), _MONTHS[m[2]], int(m[1]), int(m[4]), int(m[5]), int(m[6]), tzinfo=tz).timestamp())


def parse_access_line(line):
    m = ACCESS_RE.match(line.rstrip("\n"))
    if not m or _IPV4.match(m["tag"]):  # [127.0.0.1] = health check, not a service
        return None
    try:
        ts = _access_ts(m["ts"])
    except ValueError:
        return None
    cache = m["cache"] if m["cache"] in ("HIT", "MISS") else "NONE"
    return AccessEntry(m["tag"], m["ip"], ts, m["req"].split(" ", 1)[0], int(m["status"]),
                       int(m["bytes"]), m["ua"], cache, m["host"])


def parse_stream_line(line):
    m = STREAM_RE.match(line.rstrip("\n"))
    if not m:
        return None
    try:
        ts = _access_ts(m["ts"])
    except ValueError:
        return None
    return StreamEntry(m["ip"], ts, int(m["status"]), m["host"].lower(), int(m["sent"]),
                       int(m["recv"]), float(m["dur"]))


def _naive_ts(y, mo, d, h, mi, s, tz):
    return int(datetime(y, mo, d, h, mi, s, tzinfo=tz).timestamp())


def parse_error_line(line, tz):
    """nginx error.log. Only the cause is kept; request paths/tokens are dropped."""
    m = ERROR_RE.match(line.rstrip("\n"))
    if not m or m["level"] not in ("error", "crit", "alert", "emerg"):
        return None
    msg = m["msg"]
    cause = msg.split(", client:", 1)[0].strip()
    ip = (re.search(r"client: (\S+?),", msg) or [None, ""])[1]
    host = (re.search(r'host: "([^"]+)"', msg) or [None, ""])[1].lower()
    if "upstream timed out" in msg:
        kind = "upstream_timeout"
    elif (c := re.search(r"unexpected status code (\d{3}) in slice response", msg)):
        kind = "upstream_" + c[1]
    elif "could not be resolved" in msg:
        kind = "dns_unresolved"
        cause = re.sub(r"^\S+ could not", "host could not", cause)
    else:
        kind = "other"
    y, mo, d = (int(x) for x in m["ts"][:10].split("/"))
    hh, mi, ss = (int(x) for x in m["ts"][11:].split(":"))
    return ErrorEntry(_naive_ts(y, mo, d, hh, mi, ss, tz), kind, ip, host, cause[:200])


def parse_named_line(line, tz):
    """BIND default.log: only 'query failed' lines are interesting."""
    m = NAMED_RE.match(line.rstrip("\n"))
    if not m:
        return None
    d, mon, y = m["ts"][:11].split("-")
    hh, mi, ss = (int(x) for x in m["ts"][12:].split(":"))
    kind = "dns_" + re.sub(r"\W+", "_", m["why"]).strip("_")
    return ErrorEntry(_naive_ts(int(y), _MONTHS[mon], int(d), hh, mi, ss, tz), kind, m["ip"],
                      m["name"].lower(), "query failed (%s) %s" % (m["why"], m["rr"]))
