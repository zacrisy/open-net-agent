#!/bin/bash
# One-command VPS deploy for the live question-answering backend.
#   ./deploy/vps_deploy_brain.sh 106.14.46.145
# Optional env: VPS_USER=root VPS_KEY=~/.ssh/opennetbrain_deploy
#
# Idempotent: re-running only syncs code and restarts the service.
# Logs go to journald (`journalctl -u opennetbrain`), never into the repo.
set -euo pipefail

HOST="${1:?usage: vps_deploy_brain.sh IP [user] [key]}"
USER="${2:-${VPS_USER:-root}}"
KEY="${3:-${VPS_KEY:-$HOME/.ssh/opennetbrain_deploy}}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $USER@$HOST"
SLIP="${HOST//./-}.sslip.io"
REMOTE=/opt/opennetbrain

echo "==> sync code to $USER@$HOST:$REMOTE"
rsync -az --delete -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" \
  --exclude .git --exclude __pycache__ --exclude node_modules \
  --exclude '*.db-wal' --exclude '*.db-shm' --exclude 'brain.db*' \
  --exclude '.env' --exclude '/data/' \
  "$ROOT/" "$USER@$HOST:$REMOTE/"

echo "==> remote setup"
$SSH bash -s -- "$REMOTE" "$SLIP" <<'REMOTE_SCRIPT'
set -euo pipefail
REMOTE="$1"; SLIP="$2"; cd "$REMOTE"

# 2G swap: torch + the encoder peak around 500MB on a 894MB box.
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=20 >/dev/null
fi

# Runtime deps (CPU torch via the PyTorch CPU index; avoids ~2GB CUDA wheels).
# Tsinghua mirror: the default PyPI CDN crawls from this host.
python3 -m pip install --break-system-packages -q --prefer-binary \
  -r deploy/requirements-server.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  --extra-index-url https://download.pytorch.org/whl/cpu

# Encoder weights into the HF cache that nbpw2/dense.py reads.
if ! ls "$HOME"/.cache/huggingface/hub/models--BAAI--bge-small-en-v1.5/snapshots/*/ >/dev/null 2>&1; then
  HF_ENDPOINT=https://hf-mirror.com python3 -m huggingface_hub.commands.huggingface_cli \
    download BAAI/bge-small-en-v1.5
fi

# .env is generated once, carries the token, and is never committed.
if [ ! -f .env ]; then
  TOKEN="$(grep -oP '(?<=^Environment=TOKEN=).*' /etc/systemd/system/opennetbrain.service 2>/dev/null || true)"
  [ -n "$TOKEN" ] || TOKEN="$(openssl rand -hex 16)"
  cat > .env <<EOF
PORT=8080
TOKEN=$TOKEN
BRAIN_ASK=1
BRAIN_AUTO=1
BRAIN_DB=$REMOTE/data/brain.db
EOF
  chmod 600 .env
fi
mkdir -p data

install -m 644 deploy/open-net-brain.service /etc/systemd/system/opennetbrain.service
systemctl daemon-reload
systemctl enable opennetbrain >/dev/null
systemctl restart opennetbrain

# Wait for the engine to finish loading the pool + encoder.
for i in $(seq 1 60); do
  if curl -fsS -m 5 http://127.0.0.1:8080/public/brain/health | grep -q '"ready": *true'; then
    echo "engine ready after ${i}s"; break
  fi
  sleep 1
done
curl -fsS -m 5 http://127.0.0.1:8080/public/brain/health || true; echo

apt-get install -y -q caddy >/dev/null 2>&1 || apt-get update -q && apt-get install -y -q caddy
install -m 644 deploy/Caddyfile /etc/caddy/Caddyfile
systemctl enable caddy >/dev/null 2>&1 || true
systemctl restart caddy
echo "caddy: $(systemctl is-active caddy)"
REMOTE_SCRIPT

echo "==> waiting for HTTPS cert on https://$SLIP"
for i in $(seq 1 30); do
  if curl -fsS -m 8 "https://$SLIP/public/brain/health" >/dev/null 2>&1; then break; fi
  sleep 3
done
./deploy/healthcheck.sh "https://$SLIP" || true
echo "==> done: https://$SLIP"
