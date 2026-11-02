# -*- coding: utf-8 -*-
"""故障注入测试：错 token、节点掉线、quorum 降级。"""
import json, os, subprocess, sys, time, urllib.request, urllib.error

PORT = 8771
TOKEN = "secret"
BASE = f"http://127.0.0.1:{PORT}"


def req(path, obj=None, token=TOKEN, timeout=6):
    data = json.dumps(obj).encode() if obj is not None else None
    r = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json", "X-Auth-Token": token})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read().decode())


def main():
    procs = []
    coord = subprocess.Popen([sys.executable, "coordinator.py", str(PORT), TOKEN])
    procs.append(coord); time.sleep(0.8)
    good = []
    for i in range(2):
        p = subprocess.Popen([sys.executable, "node.py", "--coordinator", BASE, "--node-id", f"good-{i}",
                              "--index", str(i), "--total", "3", "--token", TOKEN])
        good.append(p); procs.append(p)
    bad = subprocess.Popen([sys.executable, "node.py", "--coordinator", BASE, "--node-id", "bad",
                            "--index", "2", "--total", "3", "--token", "wrong"])
    procs.append(bad); time.sleep(2.5)
    status = req("/status")
    print("nodes after bad-token attempt:", list(status["nodes"].keys()))
    assert "bad" not in status["nodes"], "wrong token should not register"
    # 错 token 查询
    try:
        req("/query", {"query": "智能体", "timeout": 2}, token="nope")
        raise AssertionError("should 401")
    except urllib.error.HTTPError as e:
        print("wrong token query ->", e.code); assert e.code == 401
    # 正常查询
    out = req("/query", {"query": "多台电脑如何组成智能体", "timeout": 5, "quorum": 2})
    print("normal results:", len(out["results"]), "score", round(out["score"], 3))
    assert len(out["results"]) >= 2
    # 杀掉一个节点，quorum=1 降级
    good[0].terminate(); time.sleep(0.5)
    out2 = req("/query", {"query": "节点加入会不会影响工作", "timeout": 4, "quorum": 1})
    print("after one node down, results:", len(out2["results"]))
    assert len(out2["results"]) >= 1
    print("metrics:", req("/metrics"))
    print("ALL TESTS PASSED")
    for p in procs:
        try: p.terminate()
        except Exception: pass


if __name__ == "__main__":
    main()
