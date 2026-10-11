"""Tiny persistent long-term memory (JSON file, keyword recall)."""
import json
import os
import re
import time


class Memory:
    def __init__(self, path: str = "memory.json"):
        self.path = path
        self.notes: list[dict] = []
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.notes = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.notes = []

    def add(self, text: str) -> None:
        self.notes.append({"ts": time.time(), "text": text})
        self._save()

    def recall(self, query: str, k: int = 3) -> list[str]:
        words = set(re.findall(r"\w+", query.lower()))
        scored = []
        for n in self.notes:
            overlap = len(words & set(re.findall(r"\w+", n["text"].lower())))
            if overlap:
                scored.append((overlap, n["ts"], n["text"]))
        scored.sort(reverse=True)
        return [t for _, _, t in scored[:k]]

    def _save(self) -> None:
        with open(self.path, "w") as f:
            json.dump(self.notes, f, indent=2)
