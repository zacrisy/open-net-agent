# -*- coding: utf-8 -*-
"""验证 starter 记忆：单节点 + docs_dir，回答加入问题。"""
import asyncio, json
import aiohttp
from aiohttp import web
import coordinator_async as C
from node_async import run

PORT = 8788

async def main():
    C.TOKENS.update({"secret"})
    runner = web.AppRunner(C.app()); await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT).start(); await asyncio.sleep(0.3)
    t = asyncio.create_task(run(f"http://127.0.0.1:{PORT}", "docs", "secret", "retrieval", 0, 1,
                                docs_dir="/tmp/prov-test2/data"))
    await asyncio.sleep(0.4)
    async with aiohttp.ClientSession() as s:
        async with s.post(f"http://127.0.0.1:{PORT}/query", json={"query": "如何加入节点", "skill": "retrieval", "timeout": 5, "quorum": 1}, headers={"X-Auth-Token": "secret"}) as r:
            d = await r.json()
            print("answer:", (d.get("answer") or "")[:100])
            print("score:", round(d.get("score", 0), 3), "results:", len(d.get("results", [])))
            assert d.get("answer") and "install.sh" in d["answer"]
    t.cancel(); await runner.cleanup()
    print("PROVISION MEMORY PASSED")

if __name__ == "__main__":
    asyncio.run(main())
