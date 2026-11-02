# -*- coding: utf-8 -*-
"""插件完整性：sha256 不匹配的插件被跳过。"""
import hashlib, json, os, tempfile
import skills

def main():
    print("loaded:", sorted(skills.SKILLS.keys()))
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "bad"))
    open(os.path.join(d, "bad", "handler.py"), "w").write("def handle(q,c): return {'answer':'BAD','score':1}\n")
    json.dump({"name": "bad", "version": "1.0", "entry": "handler.py", "func": "handle", "sha256": "0"*64},
              open(os.path.join(d, "bad", "manifest.json"), "w"))
    skills.load_plugins(d)
    print("bad loaded?", "bad" in skills.SKILLS)
    assert "bad" not in skills.SKILLS
    print("PLUGIN INTEGRITY PASSED")

if __name__ == "__main__":
    main()
