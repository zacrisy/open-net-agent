# -*- coding: utf-8 -*-
"""Executable skill registry with pre/post conditions and versioning."""
from dataclasses import dataclass, field

@dataclass
class Skill:
    name: str
    fn: object
    pre: tuple = ()
    post: tuple = ()
    cost: float = 1.0
    version: str = "0.1"
    reliability: float = 0.5
    uses: int = 0

class SkillRegistry:
    def __init__(self):
        self.skills = {}

    def register(self, skill):
        self.skills[skill.name] = skill
        return skill

    def get(self, name):
        return self.skills.get(name)

    def call(self, name, state, **kw):
        s = self.skills[name]
        if not all(state.get(k) for k in s.pre):
            return {"ok": False, "error": "precondition", "state": state}
        try:
            out = s.fn(state, **kw)
            s.uses += 1
            ok = all(out.get(k) for k in s.post) if s.post else True
            return {"ok": ok, "state": out, "skill": name}
        except Exception as e:
            return {"ok": False, "error": str(e), "state": state}
