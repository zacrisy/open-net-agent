# -*- coding: utf-8 -*-
"""WS + 异步落库 + 审计 + 插件元数据。"""
import asyncio, json, time
import aiohttp
from aiohttp import web
import coordinator_async as C

PORT = 8792

async def main():
    C.TOKENS.update({"secret"})
    runner = web.AppRunner(C.app()); await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start(); await asyncio.sleep(0.3)
    async def node():
        async with aiohttp.ClientSession() as s:
            async with s.ws_connect(f"http://127.0.0.1:{PORT}/ws?node_id=n0&token=secret&skills=echo") as ws:
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT: continue
                    d = json.loads(msg.data)
                    if d.get("type") == "task":
                        await ws.send_json({"type": "result", "task_id": d["task_id"], "node_id": "n0", "answer": d["query"], "score": 1.0})
    t = asyncio.create_task(node()); await asyncio.sleep(0.3)
    async with aiohttp.ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{PORT}/query", json={"query": "audit", "skill": "echo", "timeout": 3, "quorum": 1}, headers={"X-Auth-Token": "secret"}) as r:
            out = await r.json()
        async with s.get(f"http://127.0.0.1:{PORT}/audit?task_id={out['task_id']}") as r:
            aud = await r.json()
        async with s.get(f"http://127.0.0.1:{PORT}/skills") as r:
            sk = await r.json()
    print("skills", sk["skills"], "meta", sk["meta"].get("echo"))
    print("audit tasks", len(aud["tasks"]), "results", len(aud["results"]))
    assert aud["tasks"] and aud["results"]
    print("ASYNC AUDIT PASSED")
    t.cancel(); await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
