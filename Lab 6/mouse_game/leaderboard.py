"""Durable leaderboard stored as a JSON file next to the host."""

import json
import os
import threading
import time


class Leaderboard:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self.entries = self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def add(self, result):
        with self._lock:
            if any(e["round_id"] == result["round_id"] for e in self.entries):
                return False
            entry = dict(result)
            entry["completed_at"] = time.time()
            self.entries.append(entry)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.entries, f, indent=2)
            os.replace(tmp, self.path)
            return True

    def ranked(self, limit=10):
        with self._lock:
            ordered = sorted(
                self.entries,
                key=lambda e: (-e["score"], -e["cheese"], -e["elapsed"], e["completed_at"]),
            )
        return ordered[:limit]
