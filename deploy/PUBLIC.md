# 公网 10–50 节点试点

## 1. 服务器

- 1 台 VPS（2C4G 起），公网 IP + 域名 `coord.example.com`；
- 安全组只开 80/443，8765 不直接暴露。

## 2. Docker Compose

```bash
TOKEN=$(openssl rand -hex 16)
TOKEN=$TOKEN docker compose up -d
```

- `coordinator` 内部 8765；
- `caddy` 自动申请 HTTPS；
- 改 `deploy/Caddyfile` 的域名。

## 3. 节点加入

```bash
curl -fsSL https://raw.githubusercontent.com/your-org/netagent/main/install.sh | bash -s -- \
  --coordinator https://coord.example.com --token $TOKEN --skill retrieval
```

## 4. 运维

- `/metrics` 接 Prometheus；
- `/audit` 接日志；
- token 轮换：`coordinator.py 8765 "new,old"`，观察旧 token 流量后下线；
- 限流：Caddy rate limit / coordinator QPS；
- 滥用：白名单、邀请码、节点信誉。

## 5. 规模建议

| 阶段 | 节点 | 措施 |
|---|---|---|
| 试点 | 10–50 | 单协调者 + SQLite |
| 成长 | 50–500 | Postgres + 异步队列 |
| 大规模 | 500+ | 多协调者 + 一致性哈希 + WSS |
