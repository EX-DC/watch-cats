"""Guess a client's device type from its User-Agent. No manual input needed.

Confidence is 0..1; a higher-confidence signal replaces a lower one.
Rules marked (unverified) have not been seen in real logs yet.
"""
import re

RULES = [
    (re.compile(r"PlayStation 5"), "ps5", "PS5", 0.95),
    (re.compile(r"PlayStation ?4"), "ps4", "PS4", 0.95),
    (re.compile(r"XboxOne|Xbox One|Xbox Series|Xbox/"), "xbox_console", "Xbox", 0.6),  # (unverified)
    (re.compile(r"Windows/\d|Windows NT|Microsoft-Delivery-Optimization|Windows-Update-Agent"),
     "windows", "Windows", 0.8),
    (re.compile(r"Steam"), "pc", "PC", 0.4),
    (re.compile(r"^(curl|Wget)/"), "tool", "Tool", 0.1),
]


def detect(user_agent):
    """Return (kind, label, confidence) or None."""
    best = None
    for rx, kind, label, conf in RULES:
        if rx.search(user_agent or "") and (best is None or conf > best[2]):
            best = (kind, label, conf)
    return best
