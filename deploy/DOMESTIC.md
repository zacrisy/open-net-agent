# 国内 24/7 部署（阿里云 / 腾讯云 / 华为云轻量服务器）

> 国内云账号需要实名认证，无法自动注册。你提供一台 Ubuntu 22.04 的轻量服务器（2C2G 足够）和 SSH 后，我可以直接部署。

## 方案 A：Docker（推荐）

```bash
git clone https://github.com/zacrisy/open-net-agent.git
cd open-net-agent
docker build -t opennetbrain .
docker run -d --name opennetbrain --restart unless-stopped \
  -p 80:7860 \
  -e PORT=7860 \
  -e BRAIN_AUTO=1 \
  -e TOKEN=change-me \
  -e BRAIN_DB=/data/brain.db \
  -v opennetbrain-data:/data \
  opennetbrain
```

访问 `http://服务器IP/`；`/health` 检查。

## 方案 B：systemd + Python

```bash
sudo apt update && sudo apt install -y python3 python3-venv
git clone https://github.com/zacrisy/open-net-agent.git /opt/open-net-agent
cd /opt/open-net-agent
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

sudo tee /etc/systemd/system/opennetbrain.service >/dev/null <<'EOF'
[Unit]
Description=OpenNetBrain
After=network.target
[Service]
WorkingDirectory=/opt/open-net-agent
Environment=PORT=8080
Environment=BRAIN_AUTO=1
Environment=TOKEN=change-me
ExecStart=/opt/open-net-agent/.venv/bin/python run_online.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now opennetbrain
```

前面加 Nginx/Caddy 反代 80/443。

## 注意

- 国内服务器绑定域名通常需要 ICP 备案；直接用 IP 访问不需要。
- 安全组放行 80/443。
- `BRAIN_AUTO=1` 会在容器内每 15s 调 `auto_tick`，实现 20s 学习节奏。
- 需要把 `brain.html` 的 `PRIMARY` 改为你的服务器地址，或让 UI 与 API 同源部署。
