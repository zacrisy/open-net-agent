#!/usr/bin/env bash
set -e
cd /Users/xiaoyiyun/Desktop/研究/network_agent
for i in $(seq 1 180); do
  if gh auth status 2>/dev/null | grep -q workflow; then break; fi
  sleep 5
done
gh auth status 2>/dev/null | grep -q workflow || { echo "SCOPE_TIMEOUT"; exit 1; }
git add -f .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow" || true
for i in 1 2 3; do git -c http.version=HTTP/1.1 push origin main && break; sleep 3; done
echo "CI_PUSHED"
