# -*- coding: utf-8 -*-
"""线上启动器：协调者 + Web UI + 3 个 WS 节点。"""
import os
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
import asyncio, signal, socket
from aiohttp import web
import coordinator_async as C
from node_async import run as node_run
from skills import SKILLS
import brain

PORT = int(os.environ.get("PORT", "8080"))
TOKEN = os.environ.get("TOKEN", "secret")
NODES = [("node-echo", "echo", 0), ("node-retrieval", "retrieval", 1), ("node-nli", "nli", 2)]


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "127.0.0.1"


async def main():
    C.TOKENS.update({TOKEN})
    runner = web.AppRunner(C.app()); await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    tasks = [asyncio.create_task(node_run(f"http://127.0.0.1:{PORT}", nid, TOKEN, skill, i, 3))
             for nid, skill, i in NODES]
    import threading
    def warm():
        try:
            SKILLS["nli"]("a || a", {})
            print("nli warm ok", flush=True)
        except Exception as e:
            print("nli warm failed:", e, flush=True)
    threading.Thread(target=warm, daemon=True).start()
    brain.maybe_bootstrap()
    print(f"OpenNetAgent online: http://127.0.0.1:{PORT}/", flush=True)
    print(f"LAN: http://{lan_ip()}:{PORT}/  token={TOKEN}", flush=True)
    stop = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, stop.set)
        except Exception: pass
    await stop.wait()
    for t in tasks: t.cancel()
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
