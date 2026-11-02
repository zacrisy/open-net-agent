# -*- coding: utf-8 -*-
"""WSS 端到端：自签证书，2 节点，5 次查询。"""
import asyncio, json, ssl, time
import aiohttp
from aiohttp import web, TCPConnector
import coordinator_async as C
from node_async import run

PORT = 8443

async def main():
    C.TOKENS.update({"secret"})
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain("/tmp/wss-cert.pem", "/tmp/wss-key.pem")
    runner = web.AppRunner(C.app()); await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", PORT, ssl_context=ctx).start(); await asyncio.sleep(0.3)
    nodes = [asyncio.create_task(run(f"https://127.0.0.1:{PORT}", f"tls{i}", "secret", "echo", i, 1, insecure=True)) for i in range(2)]
    await asyncio.sleep(0.5)
    async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as s:
        lat, ok = [], 0
        for i in range(5):
            t0 = time.time()
            async with s.post(f"https://127.0.0.1:{PORT}/query", json={"query": f"tls{i}", "skill": "echo", "timeout": 5, "quorum": 2}, headers={"X-Auth-Token": "secret"}) as r:
                d = await r.json(); lat.append(time.time() - t0)
                if len(d["results"]) >= 2: ok += 1
        print("WSS success", ok / 5, "p50", round(sorted(lat)[2], 3))
    for t in nodes: t.cancel()
    await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
