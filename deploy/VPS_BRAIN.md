# VPS 常驻后端（/public/brain/ask）

目标：把 `run_online.py` 里新增的实时问答接口跑在一台常驻 VPS 上，Pages 前端直接调它。

## 现状

- 主机：`106.14.46.145`（阿里云上海，Ubuntu 24.04，2 vCPU / 894MB RAM / 30G 磁盘）
- 登录：`ssh -i ~/.ssh/opennetbrain_deploy root@106.14.46.145`
- 对外：Caddy 在 80/443 上签发 `106-14-46-145.sslip.io` 的 Let's Encrypt 证书，反代到 `127.0.0.1:8080`
- 守护：systemd `opennetbrain`（`Restart=always`，开机自启），日志进 journald
- 模型：`BAAI/bge-small-en-v1.5`（33M 参数，~130MB fp32）落在 `~/.cache/huggingface/hub/`
- 池矩阵：`nbpw2/results/bge_pool_nodes.npz`（5.7MB，3975×384 + 节点分配），随仓库同步

## 资源

| 项 | 需求 |
|---|---|
| 内存 | 常驻 ~500–600MB（torch + 编码器 + numpy 矩阵），已加 2G swap 兜底 |
| 磁盘 | 依赖约 1.2GB（CPU torch ~200MB 轮子 + 解包），模型 130MB |
| CPU | 2 核够用；单题热延迟 ~0.1–0.3s，冷启动（加载池 + 训练 head + 编码器）~7–10s |

## 一次性部署

```bash
cd network_agent
./deploy/vps_deploy_brain.sh 106.14.46.145
```

脚本是幂等的：同步代码 → 补 swap → 装依赖（CPU torch）→ 拉模型 → 生成 `.env` → 装 unit → 重启 → 等 health ready → 装 Caddy 并签证书。

## 日常

```bash
./deploy/healthcheck.sh https://106-14-46-145.sslip.io
ssh -i ~/.ssh/opennetbrain_deploy root@106.14.46.145 'journalctl -u opennetbrain -n 50 --no-pager'
ssh -i ~/.ssh/opennetbrain_deploy root@106.14.46.145 'systemctl restart opennetbrain'
```

## 密钥与日志

- `TOKEN`、`PORT`、`BRAIN_ASK` 等都在服务器 `/opt/opennetbrain/.env`（`chmod 600`），已加入 `.gitignore`，仓库里没有。
- 访问日志不进仓库；systemd 统一写 journald。接口本身不记录提问内容。

## 接口

```bash
curl -s https://106-14-46-145.sslip.io/public/brain/health
curl -s -X POST https://106-14-46-145.sslip.io/public/brain/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the population of the city where Július Satinský was born?"}'
```

限制：问题 ≤180 字符；每 IP 8 次/分钟；单次 25s 超时；抽取式答案（无 LLM 改写）。
