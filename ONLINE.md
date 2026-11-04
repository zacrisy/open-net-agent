# OpenNetAgent 线上实例

## 公网访问（已开通）

- **控制台（推荐，无隧道警告）**：<https://zacrisy.github.io/open-net-agent/brain.html?v=4>
- **后端 / 一键加入**：<https://opennetagent2.serveousercontent.com/>（serveo 固定域名；浏览器直连会看到 Serveo 警告页）

- **公网 URL**：<https://opennetagent2.serveousercontent.com/>
- **Token**：`918b9416a631d0ff91c83ac46a1fc4f8`
- 本机：<http://127.0.0.1:8080/>
- 局域网：<http://10.162.241.50:8080/>

打开公网 URL，输入 token，即可提问。

## 已验证（公网侧）

| 检查 | 结果 |
|---|---|
| `/health` | 3 节点在线 |
| 仪表盘 | `OpenNetAgent · 网络智能体` |
| 检索查询 | 返回分片检索答案 |
| NLI 查询 | `CONTRADICTION -1.0` |
| 并发 5 请求 | 5/5 成功 |

## 架构

```
浏览器 / curl（公网）
   │ HTTPS（localhost.run 隧道）
   ▼
SSH 反向隧道 → 127.0.0.1:8080
   ▼
coordinator_async.py（aiohttp）
   │ WebSocket 推送
   ├── node-echo
   ├── node-retrieval
   └── node-nli
```

- 协调者：注册、任务、quorum、Thompson 采样、审计、技能路由；
- 节点：WS 长连接，收到任务本地执行、回传；
- 隧道：`ssh -R 80:localhost:8080 nokey@localhost.run`。

## API

```bash
TOKEN=918b9416a631d0ff91c83ac46a1fc4f8
BASE=https://opennetagent2.serveousercontent.com

# 健康
curl -H "X-Auth-Token: $TOKEN" $BASE/health

# 检索
curl -X POST $BASE/query \
  -H 'Content-Type: application/json' -H "X-Auth-Token: $TOKEN" \
  -d '{"query":"多台电脑如何组成智能体","skill":"retrieval","timeout":15,"quorum":1}'

# NLI
curl -X POST $BASE/query \
  -H 'Content-Type: application/json' -H "X-Auth-Token: $TOKEN" \
  -d '{"query":"Metformin reduces glucose. || Metformin does not reduce glucose.","skill":"nli","timeout":20,"quorum":1}'
```

## 运维

```bash
# 服务
kill $(cat /tmp/netagent_online.pid)
cd /Users/xiaoyiyun/Desktop/研究/network_agent
TOKEN=$(cat /tmp/netagent_token) nohup python3 run_online.py > /tmp/netagent_online.log 2>&1 &
echo $! > /tmp/netagent_online.pid

# 隧道
kill $(cat /tmp/tunnel.pid)
nohup ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ServerAliveInterval=30 -R 80:localhost:8080 nokey@localhost.run > /tmp/tunnel.log 2>&1 &
echo $! > /tmp/tunnel.pid
grep -aoE 'https://[a-zA-Z0-9._-]+' /tmp/tunnel.log | sort -u
```

**注意**：localhost.run 免费隧道重启后 URL 会变；隧道断开则公网不可达，需重新执行上面的命令。

## 自动修复记录

1. **NLI 阻塞事件循环**：`node_async` 同步执行 NLI → 改 `asyncio.to_thread`。
2. **8080 端口占用**：`pkill` 未匹配 → `lsof -t -iTCP:8080` 精确定位。
3. **transformers 联网重试 90s**：`TRANSFORMERS_OFFLINE=1` + `HF_ENDPOINT` + 启动预加载。
4. **指标被 NLI 负分拉低**：`avg_score` → `avg_conf=max(0,score)`。

## 安全与边界

- 公网 URL 是**临时隧道**，不是正式域名；
- 已用强 token（32 hex），但**没有限流/WAF**；
- 演示语料只有 9 条，NLI 是通用小模型；
- 暴露期间任何人拿到 token 都可调用；
- 停止暴露：`kill $(cat /tmp/tunnel.pid)`；
- 生产化：Caddy/Nginx + 域名 + HTTPS + 限流 + 强 token + 白名单。

## 公网化替代方案

```bash
# cloudflared（需安装）
cloudflared tunnel --url http://localhost:8080
# Caddy 反代
coord.example.com { reverse_proxy 127.0.0.1:8080 }
# 云主机 + 安全组只开 443
```

参考 `deploy/PUBLIC.md`。
