# -*- coding: utf-8 -*-
"""WebSocket 推送 + Thompson 测试：5 节点 20 查询。"""
import asyncio, json, time
import aiohttp
from aiohttp import web
import coordinator_async as C

PORT = 8791

async def main():
    C.TOKENS.update({"secret"})
    runner = web.AppRunner(C.app()); await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT); await site.start()
    await asyncio.sleep(0.3)
    # 5 个 WS 节点
    async def node(i):
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"http://127.0.0.1:{PORT}/ws?node_id=w{i}&token=secret&skills=echo") as ws:
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT: continue
                    d = json.loads(msg.data)
                    if d.get("type") == "task":
                        await ws.send_json({"type": "result", "task_id": d["task_id"], "node_id": f"w{i}", "answer": d["query"], "score": 1.0})
    tasks = [asyncio.create_task(node(i)) for i in range(5)]
    await asyncio.sleep(0.5)
    lat, ok = [], 0
    async with aiohttp.ClientSession() as s:
        for i in range(20):
            t0 = time.time()
            async with s.post(f"http://127.0.0.1:{PORT}/query", json={"query": f"q{i}", "skill": "echo", "timeout": 5, "quorum": 5, "preferred_k": 5}, headers={"X-Auth-Token": "secret"}) as r:
                out = await r.json(); lat.append(time.time() - t0)
                if len(out["results"]) >= 5: ok += 1
    lat.sort()
    print("WS nodes 5 queries 20 success", ok / 20, "p50", round(lat[len(lat)//2], 3), "p95", round(lat[int(len(lat)*0.95)], 3))
    for t in tasks: t.cancel()
    await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
