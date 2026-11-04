#!/bin/bash
set -euo pipefail
HOST="${1:?usage: vps_deploy.sh IP [user] [key]}"
USER="${2:-root}"
KEY="${3:-$HOME/.ssh/opennetbrain_deploy}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new $USER@$HOST"
SLIP="${HOST//./-}.sslip.io"
TOKEN="$(openssl rand -hex 16)"
echo "Deploying to $USER@$HOST → https://$SLIP"
rsync -az --delete --exclude .git --exclude __pycache__ --exclude node_modules \
  --exclude '*.db-wal' --exclude '*.db-shm' "$ROOT/" "$USER@$HOST:/opt/opennetbrain/"
$SSH "apt-get update && apt-get install -y docker.io caddy"
$SSH "cd /opt/opennetbrain && docker build -t opennetbrain . && (docker rm -f opennetbrain || true) && docker run -d --restart unless-stopped --name opennetbrain -p 127.0.0.1:7860:7860 -e PORT=7860 -e BRAIN_AUTO=1 -e TOKEN=$TOKEN -e BRAIN_DB=/data/brain.db -v opennetbrain-data:/data opennetbrain"
$SSH "cat >/etc/caddy/Caddyfile <<EOF
https://$SLIP {
  reverse_proxy 127.0.0.1:7860
}
EOF
systemctl enable --now caddy && systemctl reload caddy"
echo "DONE https://$SLIP  token=$TOKEN"
