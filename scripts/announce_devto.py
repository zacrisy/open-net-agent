# -*- coding: utf-8 -*-
"""Publish promo/DEVTO.md to Dev.to. Needs DEVTO_API_KEY."""
import json, os, sys, urllib.request

KEY = os.environ.get("DEVTO_API_KEY", "")
BODY = open(os.path.join(os.path.dirname(__file__), "..", "promo", "DEVTO.md"), encoding="utf-8").read()


def main():
    dry = "--dry-run" in sys.argv
    if dry:
        print("TITLE: OpenNetAgent: an evidence-first network agent that cites real sources")
        print("BODY BYTES:", len(BODY))
        print("DRY RUN OK")
        return
    if not KEY:
        print("SKIP: set DEVTO_API_KEY")
        return
    payload = {"article": {"title": "OpenNetAgent: an evidence-first network agent that cites real sources",
                           "published": True, "body_markdown": BODY,
                           "tags": ["ai", "opensource", "agents", "python"],
                           "canonical_url": "https://github.com/zacrisy/open-net-agent"}}
    r = urllib.request.Request("https://dev.to/api/articles", data=json.dumps(payload).encode(),
                               headers={"Content-Type": "application/json", "api-key": KEY})
    with urllib.request.urlopen(r, timeout=30) as resp:
        out = json.loads(resp.read().decode())
    print("published", out.get("url"))


if __name__ == "__main__":
    main()
