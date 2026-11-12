# -*- coding: utf-8 -*-
"""Smoke tests for BMB protocol, bus, memory, skills."""
from .protocol import envelope, EventLog
from .bus import Bus
from .memory import VersionedMemory
from .skills import Skill, SkillRegistry

def main():
    m = envelope("OBSERVE", "node-a", payload={"x": 1}, prediction={"x": 0}, residual={"x": 1})
    assert m["type"] == "OBSERVE" and m["sig"].startswith("sha256:")
    log = EventLog()
    bus = Bus(log)
    bus.send("PREDICT", "node-a", prediction={"x": 0})
    bus.send("RESIDUAL", "node-a", residual={"x": 1})
    assert len(log.by_trace(m["trace"])) == 0
    assert len(log.rows) == 2

    mem = VersionedMemory()
    assert mem.put("fact A", source="s1")["status"] == "written"
    assert mem.put("fact A", source="s2")["status"] == "merged"
    k = mem.put("fact B")["id"]
    mem.rollback(1)
    assert mem.get(k) is None

    reg = SkillRegistry()
    reg.register(Skill("double", lambda s: {"x": s["x"] * 2}, pre=("x",), post=("x",)))
    assert reg.call("double", {"x": 3})["state"]["x"] == 6
    assert not reg.call("double", {})["ok"]
    print("CORE TESTS PASSED", {"messages": len(log.rows), "memory": len(mem.items), "skills": len(reg.skills)})

if __name__ == "__main__":
    main()
