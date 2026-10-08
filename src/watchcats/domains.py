"""Maps a hostname to a LanCache service using the uklans/cache-domains lists."""
import json
import os


class DomainMap:
    def __init__(self):
        self._exact = {}
        self._suffix = []  # (".example.com", service)

    @classmethod
    def load(cls, directory):
        dm = cls()
        with open(os.path.join(directory, "cache_domains.json"), encoding="utf-8") as f:
            data = json.load(f)
        entries = data["cache_domains"] if isinstance(data, dict) else data
        for entry in entries:
            for fname in entry.get("domain_files", []):
                path = os.path.join(directory, fname)
                if not os.path.exists(path):
                    continue
                with open(path, encoding="utf-8") as g:
                    for line in g:
                        dm.add(line.strip(), entry["name"])
        dm._suffix.sort(key=lambda t: -len(t[0]))
        return dm

    def add(self, pattern, service):
        pattern = pattern.strip().lower()
        if not pattern or pattern.startswith("#"):
            return
        if pattern.startswith("*."):
            self._suffix.append((pattern[1:], service))
        else:
            self._exact[pattern] = service

    def lookup(self, host):
        host = (host or "").lower().rstrip(".")
        if host in self._exact:
            return self._exact[host]
        for suffix, service in self._suffix:
            if host.endswith(suffix):
                return service
        return None
