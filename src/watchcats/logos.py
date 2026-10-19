"""Optional: copy service logos (SVG) into the dashboard.

Source: a folder of Simple Icons files (https://simpleicons.org, the icon files are CC0; the logos themselves
are trademarks of their owners and are only used to identify each service). You can also drop any
`<service key>.svg|png|webp` into web/logos by hand.
"""
import shutil
from pathlib import Path

DEST = Path(__file__).resolve().parent / "web" / "logos"
# service key used by Watch Cats -> file names (without .svg) to try, in order
CANDIDATES = {
    "steam": ["steam"], "epicgames": ["epicgames"], "sony": ["playstation"],
    "wsus": ["windows", "windows11", "microsoft"], "xboxlive": ["xbox"], "riot": ["riotgames"],
    "uplay": ["ubisoft"], "origin": ["ea"], "blizzard": ["battledotnet", "blizzard"],
    "rockstar": ["rockstargames"], "cod": ["callofduty"], "nintendo": ["nintendo"],
    "wargaming": ["wargaming"], "warframe": ["warframe"], "nexusmods": ["nexusmods"],
    "square": ["squareenix"], "pathofexile": ["pathofexile"],
}


def _is_safe_svg(path):
    try:
        if path.stat().st_size > 100_000:
            return False
        text = path.read_text(encoding="utf-8", errors="strict").lower()
    except (OSError, UnicodeDecodeError):
        return False
    return "<svg" in text and "<script" not in text and "onload" not in text and "javascript:" not in text


def install(src_dir, dest_dir=DEST):
    """Returns ({key: file used}, [keys with no matching file])."""
    src, dest = Path(src_dir), Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    copied, missing = {}, []
    for key, names in CANDIDATES.items():
        for n in names:
            f = src / (n + ".svg")
            if f.is_file() and _is_safe_svg(f):
                shutil.copyfile(f, dest / (key + ".svg"))
                copied[key] = f.name
                break
        else:
            missing.append(key)
    return copied, missing
