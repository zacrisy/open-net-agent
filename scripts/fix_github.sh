#!/bin/bash
# 受限网络下的 GitHub 修复：SSH over 443 优先，HTTPS 本地代理兜底
set -e
cd "$(dirname "$0")/.."
REPO="zacrisy/open-net-agent"

# 1) ensure deploy key
if [ ! -f "$HOME/.ssh/github_deploy" ]; then
  ssh-keygen -t ed25519 -f "$HOME/.ssh/github_deploy" -N "" -C "opennetagent-deploy" >/dev/null
  echo "new key: $(cat "$HOME/.ssh/github_deploy.pub")"
  echo "add it as a deploy key: gh api -X POST repos/$REPO/keys -f title=opennetagent-deploy -f key=\"$(cat "$HOME/.ssh/github_deploy.pub")\" -F read_only=false"
fi

# 2) SSH alias over 443
if ! grep -q "Host github-opennet" "$HOME/.ssh/config" 2>/dev/null; then
  cat >> "$HOME/.ssh/config" <<'CFG'

Host github-opennet
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
CFG
  chmod 600 "$HOME/.ssh/config"
fi

# 3) prefer SSH
if timeout 12 ssh -T git@github-opennet 2>&1 | grep -q "successfully authenticated"; then
  git remote set-url origin "git@github-opennet:$REPO.git"
  git ls-remote origin HEAD >/dev/null
  echo "GitHub OK via SSH over 443"
  exit 0
fi

# 4) fallback: HTTPS via local proxy
if ! pgrep -f ghproxy.py >/dev/null 2>&1; then
  nohup python3 ghproxy.py >/tmp/ghproxy.log 2>&1 &
  sleep 1
fi
git remote set-url origin "https://github.com/$REPO.git"
git config --global http.https://github.com.proxy http://127.0.0.1:8899
git config --global https.https://github.com.proxy http://127.0.0.1:8899
git config --global http.https://github.com.version HTTP/1.1
git ls-remote origin HEAD >/dev/null
echo "GitHub OK via HTTPS proxy"
