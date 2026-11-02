# -*- coding: utf-8 -*-
"""50 节点 WS 试点模拟：100 次查询。"""
import asyncio, json, time
import aiohttp
from aiohttp import web
import coordinator_async as C

PORT = 8793; N = 50; Q = 100

async def main():
    C.TOKENS.update({"secret"})
    runner = web.AppRunner(C.app()); await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start(); await asyncio.sleep(0.3)
    async def node(i):
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"http://127.0.0.1:{PORT}/ws?node_id=n{i}&token=secret&skills=echo") as ws:
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT: continue
                    d = json.loads(msg.data)
                    if d.get("type") == "task":
                        await ws.send_json({"type": "result", "task_id": d["task_id"], "node_id": f"n{i}", "answer": d["query"], "score": 1.0})
    tasks = [asyncio.create_task(node(i)) for i in range(N)]
    await asyncio.sleep(0.8)
    lat, ok = [], 0
    async with aiohttp.ClientSession() as s:
        for i in range(Q):
            t0 = time.time()
            async with s.post(f"http://127.0.0.1:{PORT}/query", json={"query": f"q{i}", "skill": "echo", "timeout": 8, "quorum": N, "preferred_k": N}, headers={"X-Auth-Token": "secret"}) as r:
                out = await r.json(); lat.append(time.time() - t0)
                if len(out["results"]) >= N: ok += 1
    lat.sort()
    print("WS nodes", N, "queries", Q, "success", ok / Q, "p50", round(lat[len(lat)//2], 4), "p95", round(lat[int(len(lat)*0.95)], 4))
    for t in tasks: t.cancel()
    await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
