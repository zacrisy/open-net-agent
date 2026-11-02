# -*- coding: utf-8 -*-
"""沙箱测试：慢插件被超时终止，正常插件可用。"""
import json, os, tempfile, time
os.environ["SANDBOX"] = "1"
import skills

def make(name, body):
    d = tempfile.mkdtemp(); p = os.path.join(d, name); os.makedirs(p)
    open(os.path.join(p, "handler.py"), "w").write(body)
    import hashlib
    h = hashlib.sha256(open(os.path.join(p, "handler.py"), "rb").read()).hexdigest()
    json.dump({"name": name, "version": "1.0", "entry": "handler.py", "func": "handle", "sha256": h},
              open(os.path.join(p, "manifest.json"), "w"))
    return d

good = make("good", "def handle(q, c): return {'answer': q, 'score': 1.0}\n")
slow = make("slow", "import time\ndef handle(q, c):\n    time.sleep(5)\n    return {'answer': 'late', 'score': 1.0}\n")
skills.load_plugins(good); skills.load_plugins(slow)
print("good:", skills.SKILLS["good"]("hi", {}))
t0 = time.time(); out = skills.SKILLS["slow"]("hi", {}); dt = time.time() - t0
print("slow:", out, "elapsed", round(dt, 2))
assert out.get("error") == "timeout" and dt < 4
print("SANDBOX PASSED")
