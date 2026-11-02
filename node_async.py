# -*- coding: utf-8 -*-
"""异步 WS 节点。"""
import argparse, asyncio, json, os, random
import aiohttp
from skills import SKILLS
from corpus import shard

async def run(url, nid, token, skill, index, total, latency_ms=0, drop=0):
    docs = shard(index, total)
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.ws_connect(f"{url}/ws?node_id={nid}&token={token}&skills={skill}", heartbeat=20) as ws:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT: continue
                        d = json.loads(msg.data)
                        if d.get("type") != "task": continue
                        if drop and random.random() < drop: continue
                        if latency_ms: await asyncio.sleep(latency_ms / 1000)
                        out = SKILLS[skill](d["query"], {"docs": docs})
                        await ws.send_json({"type": "result", "task_id": d["task_id"], "node_id": nid,
                                            "answer": out.get("answer"), "score": out.get("score", 0)})
        except Exception:
            await asyncio.sleep(1)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--node-id", default=f"a-{os.getpid()}")
    ap.add_argument("--token", default=""); ap.add_argument("--skill", default="echo")
    ap.add_argument("--index", type=int, default=0); ap.add_argument("--total", type=int, default=1)
    ap.add_argument("--latency-ms", type=float, default=0); ap.add_argument("--drop", type=float, default=0)
    a = ap.parse_args()
    asyncio.run(run(a.url, a.node_id, a.token, a.skill, a.index, a.total, a.latency_ms, a.drop))
