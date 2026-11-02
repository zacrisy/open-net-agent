# -*- coding: utf-8 -*-
"""节点自动配置：检测硬件、拉取 starter 记忆、选择 skills、写配置。"""
import argparse, json, os, platform, shutil, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def ram_gb():
    try:
        if platform.system() == "Darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
            return int(out) / (1024 ** 3)
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / (1024 ** 3)
    except Exception:
        return 2.0


def disk_gb(path):
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except Exception:
        return 10.0


def can_nli():
    try:
        import transformers  # noqa
        import torch  # noqa
        return True
    except Exception:
        return False


def fetch_starter(coord):
    for _ in range(4):
        try:
            with urllib.request.urlopen(coord.rstrip("/") + "/starter_corpus.json", timeout=10) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(1)
    try:
        from corpus import DOCS
        return DOCS
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coordinator", required=True)
    ap.add_argument("--dir", default=os.path.expanduser("~/.netagent"))
    ap.add_argument("--profile", default="auto", choices=["auto", "lite", "full"])
    ap.add_argument("--with-nli", action="store_true")
    ap.add_argument("--data-dir", default=None, help="可选：接入自己的文档目录")
    a = ap.parse_args()

    os.makedirs(os.path.join(a.dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(a.dir, "models"), exist_ok=True)
    ram = ram_gb(); free = disk_gb(a.dir)
    nli_ok = can_nli()

    if a.profile == "lite":
        skills = ["retrieval", "echo"]
    elif a.profile == "full":
        skills = ["retrieval", "echo"] + (["nli"] if nli_ok else [])
    else:
        skills = ["retrieval", "echo"]
        if ram >= 4 and free >= 2 and nli_ok:
            skills.append("nli")

    if a.with_nli and "nli" not in skills:
        if nli_ok:
            skills.append("nli")
        else:
            print("NLI deps missing: pip install -r requirements-nli.txt", flush=True)

    docs = fetch_starter(a.coordinator)
    docs_path = os.path.join(a.dir, "data", "docs.json")
    json.dump(docs, open(docs_path, "w"), ensure_ascii=False, indent=1)
    if a.data_dir and os.path.isdir(a.data_dir):
        extra = []
        for root, _, files in os.walk(a.data_dir):
            for f in files:
                if f.endswith((".txt", ".md")):
                    try: extra.append(open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()[:4000])
                    except Exception: pass
        if extra:
            json.dump(docs + extra, open(docs_path, "w"), ensure_ascii=False, indent=1)
            print(f"indexed {len(extra)} local docs", flush=True)

    cfg = {"coordinator": a.coordinator, "profile": a.profile, "skills": skills,
           "docs_dir": os.path.join(a.dir, "data"), "docs_count": len(docs) + (len(extra) if a.data_dir else 0),
           "ram_gb": round(ram, 1), "free_gb": round(free, 1), "nli_deps": nli_ok}
    json.dump(cfg, open(os.path.join(a.dir, "config.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(cfg, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
