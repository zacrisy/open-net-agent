#!/bin/bash
set -euo pipefail
: "${HF_TOKEN:?set HF_TOKEN (write token)}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
rsync -a --exclude .git --exclude __pycache__ --exclude node_modules --exclude '*.db-wal' --exclude '*.db-shm' "$ROOT"/ "$TMP"/
cat > "$TMP/README.md" <<EOF
---
title: OpenNetBrain
emoji: 🧠
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# OpenNetBrain

A network-native continual learner: real sources → knowledge cards → belief graph → tools.
EOF
HF_TOKEN="$HF_TOKEN" SPACE="${SPACE:-}" TMP="$TMP" python3 - <<'PY'
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
space = os.environ.get("SPACE") or (api.whoami()["name"] + "/open-net-brain")
api.create_repo(repo_id=space, repo_type="space", space_sdk="docker", exist_ok=True)
api.upload_folder(repo_id=space, repo_type="space", folder_path=os.environ["TMP"], commit_message="OpenNetBrain Docker Space")
print("SPACE_URL=https://huggingface.co/spaces/" + space)
print("DIRECT_URL=https://" + space.replace("/", "-") + ".hf.space")
PY
