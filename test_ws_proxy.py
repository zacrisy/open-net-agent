# -*- coding: utf-8 -*-
"""WS + 传输层 WAN 代理：5 节点、30ms、5% 丢包。"""
import asyncio, json, threading, time
import aiohttp
from aiohttp import web
import coordinator_async as C
from netproxy import serve as proxy_serve

COORD = 8794; PROXY = 8795; N = 5

async def main():
    C.TOKENS.update({"secret"})
    runner = web.AppRunner(C.app()); await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", COORD).start(); await asyncio.sleep(0.3)
    threading.Thread(target=proxy_serve, args=(PROXY, ("127.0.0.1", COORD), 30, 0.05), daemon=True).start()
    async def node(i):
        while True:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.ws_connect(f"http://127.0.0.1:{PROXY}/ws?node_id=p{i}&token=secret&skills=echo") as ws:
                        async for msg in ws:
                            if msg.type != aiohttp.WSMsgType.TEXT: continue
                            d = json.loads(msg.data)
                            if d.get("type") == "task":
                                await ws.send_json({"type": "result", "task_id": d["task_id"], "node_id": f"p{i}", "answer": d["query"], "score": 1.0})
            except Exception:
                await asyncio.sleep(0.5)
    tasks = [asyncio.create_task(node(i)) for i in range(N)]
    await asyncio.sleep(1.5)
    for Q in [5, 4, 3]:
        lat, ok = [], 0
        async with aiohttp.ClientSession() as s:
            for i in range(10):
                t0 = time.time()
                async with s.post(f"http://127.0.0.1:{COORD}/query", json={"query": f"q{i}", "skill": "echo", "timeout": 8, "quorum": Q, "preferred_k": N}, headers={"X-Auth-Token": "secret"}) as r:
                    out = await r.json(); lat.append(time.time() - t0)
                    if len(out["results"]) >= Q: ok += 1
        lat.sort()
        print("WS proxy 30ms/5% quorum", Q, "success", ok / 10, "p50", round(lat[len(lat)//2], 3), "p95", round(lat[int(len(lat)*0.95)], 3))
    for t in tasks: t.cancel()
    await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
