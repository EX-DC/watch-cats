"""Display names and the Xbox console/Windows split."""

NAMES = {
    "steam": "Steam", "epicgames": "Epic Games", "sony": "PlayStation", "wsus": "Windows Update",
    "xboxlive": "Xbox", "xbox_console": "Xbox (console)", "xbox_windows": "Xbox / Store (Windows)",
    "riot": "Riot Games", "uplay": "Ubisoft", "origin": "EA / Origin", "blizzard": "Blizzard",
    "rockstar": "Rockstar", "cod": "Call of Duty", "nintendo": "Nintendo", "wargaming": "Wargaming",
    "warframe": "Warframe", "arenanet": "ArenaNet", "bsg": "Battlestate", "cityofheroes": "City of Heroes",
    "daybreak": "Daybreak", "frontier": "Frontier", "neverwinter": "Neverwinter", "nexusmods": "Nexus Mods",
    "pathofexile": "Path of Exile", "renegadex": "Renegade X", "square": "Square Enix", "teso": "TESO",
    "other": "Other",
}


def display_key(tag, device_kind):
    """LanCache's 'xboxlive' tag is split by who asked for it (best effort)."""
    if tag == "xboxlive":
        if device_kind == "xbox_console":
            return "xbox_console"
        if device_kind == "windows":
            return "xbox_windows"
    return tag


def name(key):
    return NAMES.get(key, key)
