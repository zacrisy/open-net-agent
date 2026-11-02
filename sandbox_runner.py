# -*- coding: utf-8 -*-
"""在子进程中执行插件：stdin JSON -> handler -> stdout JSON。"""
import importlib.util, json, os, sys

def main():
    path, func = sys.argv[1], sys.argv[2]
    spec = importlib.util.spec_from_file_location("plugin_sandbox", path)
    mod = importlib.util.module_from_spec(spec)
    os.environ["SANDBOX"] = "0"  # 避免 handler 内 import skills 时递归
    spec.loader.exec_module(mod)
    data = json.load(sys.stdin)
    out = getattr(mod, func)(data.get("query", ""), data.get("ctx", {}))
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
