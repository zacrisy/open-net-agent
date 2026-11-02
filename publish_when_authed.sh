#!/usr/bin/env bash
set -e
cd /Users/xiaoyiyun/Desktop/研究/network_agent
for i in $(seq 1 180); do
  if gh auth status >/dev/null 2>&1; then break; fi
  sleep 5
done
gh auth status >/dev/null 2>&1 || { echo "AUTH_TIMEOUT"; exit 1; }
USER=$(gh api user --jq .login)
echo "AUTHED $USER"
git config user.name "$USER"
git config user.email "$USER@users.noreply.github.com"
git branch -M main
if ! gh repo view "$USER/open-net-agent" >/dev/null 2>&1; then
  gh repo create open-net-agent --public --source=. --remote=origin --push
else
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$USER/open-net-agent.git"
  git push -u origin main
fi
git push origin v0.5.0 || true
gh release create v0.5.0 dist/open-net-agent-v0.5.0.tar.gz --title "v0.5.0" --notes-file CHANGELOG.md 2>/dev/null || true
gh repo edit --description "OpenNetAgent: turn computers into nodes of a network-native agent (WebSocket, quorum, skills)." 2>/dev/null || true
gh repo edit --add-topic multi-agent --add-topic distributed-systems --add-topic websocket --add-topic ai-agents --add-topic python 2>/dev/null || true
echo "DONE https://github.com/$USER/open-net-agent"
