# -*- coding: utf-8 -*-
"""Post the OpenNetAgent launch thread to Bluesky.
Needs BLUESKY_HANDLE and BLUESKY_APP_PASSWORD.
Run with --dry-run to preview.
"""
import datetime, json, os, re, sys, urllib.request

HANDLE = os.environ.get("BLUESKY_HANDLE", "")
PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")
API = "https://bsky.social/xrpc"

POSTS = [
    "Most agents are one model on one machine. OpenNetAgent treats each computer as a node, connected as a graph. The network is the agent. 🧵",
    "It answers with real sources: PubMed, arXiv, Hacker News, Stack Overflow, OpenAlex, Crossref — with [n] citations. GLP-1 mechanism: 4 papers, ~11s.",
    "Also: document Q&A with [Dn], AST-safe compute, and NLI claim verification. Not a chatbot; a workbench.",
    "A 0.5B local model invented facts in testing, so facts come from retrieval; the model is optional. Evidence first, not vibes.",
    "Upvote an answer → experience → knowledge pack → new nodes pull it → later answers cite “network memory”.",
    "Try it: https://tinyurl.com/2bfybazp\nRepo: https://github.com/zacrisy/open-net-agent\nLooking for node runners + contributors.",
]


def facets(text):
    out = []
    for m in re.finditer(r"https?://[^\s]+", text):
        url = m.group(0).rstrip(".,)")
        start = len(text[:m.start()].encode("utf-8"))
        end = start + len(url.encode("utf-8"))
        out.append({"index": {"byteStart": start, "byteEnd": end},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]})
    return out


def req(url, payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(url, data=data, headers=headers or {"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=20) as resp:
        return json.loads(resp.read().decode())


def main():
    dry = "--dry-run" in sys.argv
    for i, p in enumerate(POSTS, 1):
        print(f"[{i}/{len(POSTS)}] {p}\n")
    if dry:
        print("DRY RUN OK")
        return
    if not HANDLE or not PASSWORD:
        print("SKIP: set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD")
        return
    s = req(f"{API}/com.atproto.server.createSession", {"identifier": HANDLE, "password": PASSWORD})
    jwt = s["accessJwt"]; did = s["did"]
    h = {"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"}
    root = parent = None
    for text in POSTS:
        rec = {"$type": "app.bsky.feed.post", "text": text[:300],
               "createdAt": datetime.datetime.utcnow().isoformat() + "Z"}
        f = facets(rec["text"])
        if f: rec["facets"] = f
        if parent:
            rec["reply"] = {"root": root, "parent": parent}
        out = req(f"{API}/com.atproto.repo.createRecord",
                  {"repo": did, "collection": "app.bsky.feed.post", "record": rec}, h)
        curs = {"uri": out["uri"], "cid": out["cid"]}
        if not root:
            root = curs
        parent = curs
        print("posted", out["uri"])
    print("DONE")


if __name__ == "__main__":
    main()
