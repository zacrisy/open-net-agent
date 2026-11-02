# OpenNetAgent 线上实例

## 访问

- 本机：<http://127.0.0.1:8080/>
- 局域网：<http://10.162.241.50:8080/>
- Token：`secret`（演示用，生产请改）

进程 PID 见 `/tmp/netagent_online.pid`；日志 `/tmp/netagent_online.log`。

## 架构

```
浏览器 / curl
   │  HTTP
   ▼
coordinator_async.py（aiohttp）
   │  WebSocket 推送任务
   ├── node-echo       （连通性）
   ├── node-retrieval  （本地分片检索）
   └── node-nli        （NLI 支持/反驳）
```

- 协调者：注册、任务、quorum、Thompson 采样、审计、技能路由；
- 节点：WebSocket 长连接，收到任务后本地执行，结果回传；
- 仪表盘：提问、状态、节点、审计。

## 用法

### 仪表盘

打开 <http://127.0.0.1:8080/>，输入 token，选择技能，提问。

### API

```bash
# 健康
curl -H "X-Auth-Token: secret" http://127.0.0.1:8080/health

# 检索
curl -X POST http://127.0.0.1:8080/query \
  -H 'Content-Type: application/json' -H 'X-Auth-Token: secret' \
  -d '{"query":"多台电脑如何组成智能体","skill":"retrieval","timeout":10,"quorum":1}'

# NLI
curl -X POST http://127.0.0.1:8080/query \
  -H 'Content-Type: application/json' -H 'X-Auth-Token: secret' \
  -d '{"query":"Metformin reduces glucose. || Metformin does not reduce glucose.","skill":"nli","timeout":30,"quorum":1}'

# 审计
curl -H "X-Auth-Token: secret" http://127.0.0.1:8080/audit
```

## 自动修复记录

1. **NLI 阻塞事件循环**：`node_async` 同步执行 NLI，导致协调者卡死 → 改 `asyncio.to_thread`。
2. **8080 端口占用**：`pkill` 未匹配 → 用 `lsof -t -iTCP:8080` 精确定位并 kill。
3. **transformers 联网重试 90s**：设置 `TRANSFORMERS_OFFLINE=1` + `HF_ENDPOINT`，启动时预加载 NLI。
4. **指标被 NLI 负分拉低**：`avg_score` → `avg_conf=max(0,score)`。

## 运维

```bash
# 停止
kill $(cat /tmp/netagent_online.pid)

# 重启
cd /Users/xiaoyiyun/Desktop/研究/network_agent
nohup python3 run_online.py > /tmp/netagent_online.log 2>&1 &
echo $! > /tmp/netagent_online.pid

# 看日志
tail -f /tmp/netagent_online.log
```

## 局限与安全

- 当前是**本机/局域网**实例，未开公网隧道；
- HTTP 不是 HTTPS；生产用 Caddy/Nginx 反代；
- token 默认 `secret`，公网前必须改；
- 演示语料只有 9 条，NLI 是通用小模型；
- 公网暴露前请加：HTTPS、强 token、限流、白名单。

## 公网化

```bash
# 方案 A：Caddy 反代 + 域名
# 方案 B：cloudflared tunnel --url http://localhost:8080
# 方案 C：云主机 + 安全组只开 443
```

参考 `deploy/PUBLIC.md`。
