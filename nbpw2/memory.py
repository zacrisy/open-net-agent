# -*- coding: utf-8 -*-
"""Versioned memory with novelty gate and rollback."""
import hashlib, time

class VersionedMemory:
    def __init__(self, threshold=0.82):
        self.items = {}
        self.versions = []
        self.threshold = threshold

    def _key(self, text):
        return hashlib.sha256(text.encode()).hexdigest()[:12]

    def put(self, text, source="", confidence=0.5, force=False):
        k = self._key(text)
        if not force and k in self.items:
            self.items[k]["support"] += 1
            return {"status": "merged", "id": k}
        self.items[k] = {"id": k, "text": text, "source": source, "confidence": confidence,
                         "support": 1, "ts": time.time(), "version": len(self.versions) + 1}
        self.versions.append(k)
        return {"status": "written", "id": k}

    def rollback(self, n=1):
        for _ in range(min(n, len(self.versions))):
            k = self.versions.pop()
            self.items.pop(k, None)

    def get(self, k):
        return self.items.get(k)
