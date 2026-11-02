#!/bin/bash
# 修复受限网络下的 GitHub 连接：本地 CONNECT 代理 + 多 IP 故障切换
set -e
cd "$(dirname "$0")/.."
if ! pgrep -f ghproxy.py >/dev/null 2>&1; then
  nohup python3 ghproxy.py >/tmp/ghproxy.log 2>&1 &
  sleep 1
fi
git config --global http.https://github.com.proxy http://127.0.0.1:8899
git config --global https.https://github.com.proxy http://127.0.0.1:8899
git config --global http.https://github.com.version HTTP/1.1
echo "proxy: $(curl -x http://127.0.0.1:8899 -sI --max-time 8 https://github.com | head -1)"
git ls-remote origin HEAD >/dev/null && echo "GitHub OK"
