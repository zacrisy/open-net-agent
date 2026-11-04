#!/bin/bash
# Run as root in the cloud console web terminal.
set -euo pipefail

PUBKEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICxpBQslnduoVith/if9P5gX8bKb1mJoX9/pPa7R5vZF opennetbrain-deploy"

mkdir -p /root/.ssh
touch /root/.ssh/authorized_keys
grep -qF "$PUBKEY" /root/.ssh/authorized_keys || echo "$PUBKEY" >> /root/.ssh/authorized_keys
chmod 700 /root/.ssh; chmod 600 /root/.ssh/authorized_keys

apt-get update
apt-get install -y docker.io git curl openssl
systemctl enable --now docker

rm -rf /opt/opennetbrain
git clone --depth 1 https://github.com/zacrisy/open-net-agent.git /opt/opennetbrain || \
  git clone --depth 1 https://ghproxy.com/https://github.com/zacrisy/open-net-agent.git /opt/opennetbrain
cd /opt/opennetbrain

TOKEN="$(openssl rand -hex 16)"
docker build -t opennetbrain .
docker rm -f opennetbrain 2>/dev/null || true
docker run -d --restart unless-stopped --name opennetbrain \
  -p 127.0.0.1:7860:7860 \
  -e PORT=7860 -e BRAIN_AUTO=1 -e TOKEN="$TOKEN" -e BRAIN_DB=/data/brain.db \
  -v opennetbrain-data:/data opennetbrain

IP="$(curl -s --max-time 10 https://api.ipify.org || hostname -I | awk '{print $1}')"
SLIP="${IP//./-}.sslip.io"
cat > /opt/opennetbrain/Caddyfile <<EOF
https://$SLIP {
  reverse_proxy 127.0.0.1:7860
}
EOF
docker rm -f caddy 2>/dev/null || true
docker run -d --restart unless-stopped --name caddy --network host \
  -v /opt/opennetbrain/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy_data:/data caddy:2

sleep 3
echo "================================================"
echo "DONE"
echo "HTTPS: https://$SLIP"
echo "HTTP : http://$IP:7860"
echo "TOKEN: $TOKEN"
echo "Keep security group ports 80/443 (and 7860 for fallback) open."
echo "================================================"
