# -*- coding: utf-8 -*-
"""插件沙箱：子进程 + 超时 + 内存上限。"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "sandbox_runner.py")
TIMEOUT = float(os.environ.get("PLUGIN_TIMEOUT", "2"))
MEM_MB = int(os.environ.get("PLUGIN_MEM_MB", "256"))


def _limit():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEM_MB * 1024 * 1024, MEM_MB * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (int(TIMEOUT) + 1, int(TIMEOUT) + 2))
    except Exception:
        pass


def run_in_sandbox(handler_path, func, query, ctx):
    try:
        p = subprocess.run([sys.executable, RUNNER, handler_path, func],
                           input=json.dumps({"query": query, "ctx": ctx}, ensure_ascii=False),
                           text=True, capture_output=True, timeout=TIMEOUT, preexec_fn=_limit)
        if p.returncode != 0:
            return {"answer": None, "score": 0.0, "error": (p.stderr or "plugin failed")[-300:]}
        return json.loads(p.stdout)
    except subprocess.TimeoutExpired:
        return {"answer": None, "score": 0.0, "error": "timeout"}
    except Exception as e:
        return {"answer": None, "score": 0.0, "error": str(e)}
