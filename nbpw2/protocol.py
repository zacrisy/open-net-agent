# -*- coding: utf-8 -*-
"""BMB v0 message envelope + append-only event log."""
import json, hashlib, time, uuid

TYPES = {"OBSERVE", "PREDICT", "RESIDUAL", "QUERY", "PROPOSE", "VERIFY",
         "MEMORY_READ", "MEMORY_WRITE", "SKILL_CALL", "VOTE", "REWARD",
         "TOPO", "HEARTBEAT", "BACKPRESSURE"}

def _hash(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

def envelope(type_, src, dst="workspace", payload=None, prediction=None, residual=None,
             precision=0.5, confidence=0.5, budget=None, parent=None, trace=None, cap=None):
    if type_ not in TYPES:
        raise ValueError(f"unknown message type: {type_}")
    m = {
        "id": "m-" + uuid.uuid4().hex[:12],
        "parent": parent, "trace": trace or ("t-" + uuid.uuid4().hex[:10]),
        "type": type_, "src": src, "dst": dst, "cap": cap or [],
        "epoch": int(time.time() * 1000), "ttl": 8,
        "payload": payload or {}, "prediction": prediction or {},
        "residual": residual or {}, "precision": float(precision),
        "confidence": float(confidence),
        "budget": budget or {"bytes": 4096, "deadline_ms": 800},
        "sig": "",
    }
    m["sig"] = "sha256:" + _hash({k: v for k, v in m.items() if k != "sig"})
    return m

class EventLog:
    """In-memory/JSONL append-only log with replay."""
    def __init__(self, path=None):
        self.path = path
        self.rows = []
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    self.rows = [json.loads(x) for x in f if x.strip()]
            except FileNotFoundError:
                pass

    def append(self, msg):
        self.rows.append(msg)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        return msg

    def by_trace(self, trace):
        return [m for m in self.rows if m.get("trace") == trace]

    def replay(self, trace):
        return sorted(self.by_trace(trace), key=lambda m: m.get("epoch", 0))
