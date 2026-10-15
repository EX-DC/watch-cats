"""Optional: download the Vazirmatn font (a Persian UI font) next to the web files.

The dashboard works without it (it falls back to system fonts); with it, Persian text looks the same
on every computer. The file is not stored in git.
"""
import urllib.request
from pathlib import Path

FONT_URL = "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/fonts/webfonts/Vazirmatn%5Bwght%5D.woff2"
DEST = Path(__file__).resolve().parent / "web" / "fonts" / "Vazirmatn.woff2"


def install(url=FONT_URL, dest=DEST, timeout=30):
    """Download and sanity-check the font. Returns the size in bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": "watch-cats"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(5_000_000)
    if data[:4] != b"wOF2" or len(data) < 20_000:
        raise ValueError("the downloaded file is not a WOFF2 font")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return len(data)
