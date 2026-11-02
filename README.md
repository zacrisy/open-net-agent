# OpenNetAgent（织网）

> 把互联网上的电脑组织成一个**可加入、可退出、低打扰、可验证**的网络智能体。
> 不是“把一台电脑变大”，而是“让很多台电脑像专家网络一样互相路由、聚合、验证”。

## 1. 思想

单机模型受内存/算力限制；生物智能不是“一个超大神经元”，而是**大量单元 + 连接 + 活动**。

我们把每台电脑看成一个**节点（Node）**：

- 有自己的本地记忆/模型/工具；
- 通过**出站连接**加入网络；
- 收到任务后本地计算，只返回结果/证据/分数；
- 协调者做**路由、聚合、验证**；
- 节点可随时暂停、退出、卸载。

**关键抽象**：不是字面意义的“大神经网络”，而是**图上的智能体网络**（节点=能力单元，边=消息，聚合=注意力，验证=裁判）。

## 2. 目标

| 目标 | 说明 |
|---|---|
| 开放 | 任何人可加入、可退出、可审计 |
| 一键 | 一条命令安装为后台服务 |
| 低打扰 | 出站轮询、nice 19、限并发、可暂停 |
| 隐私 | 不共享原始文件，只回任务所需片段 |
| 可扩展 | 技能插件：检索、NLI、问答、工具 |
| 可验证 | 结果带证据与置信度，协调者复核 |

**非目标**：不跑任意代码、不挖矿、不采集用户数据、不做“自动真理机”。

## 3. 架构

```
                 ┌──────────────────────────┐
                 │ Coordinator（协调者）      │
                 │ 注册 / 任务 / 聚合 / 验证  │
                 └───────┬──────────────────┘
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
   │ Node A  │      │ Node B  │      │ Node C  │
   │ 本地记忆 │      │ 本地模型 │      │ 本地工具 │
   └─────────┘      └─────────┘      └─────────┘
```

- **Coordinator**：`coordinator.py`，HTTP 服务；节点注册、心跳、任务分发、结果聚合。
- **Node**：`node.py`，出站轮询；本地技能；结果上报。
- **Installer**：`install.sh`，一键安装为 launchd/systemd/nohup 服务。
- **Skill**：默认 `retrieval`（本地小语料关键词检索），可替换为向量检索/NLI/QA。

## 4. 快速开始（本机）

```bash
# 终端 1：协调者
python3 coordinator.py 8765

# 终端 2/3/4：三个节点（分片）
python3 node.py --coordinator http://127.0.0.1:8765 --node-id node-0 --index 0 --total 3
python3 node.py --coordinator http://127.0.0.1:8765 --node-id node-1 --index 1 --total 3
python3 node.py --coordinator http://127.0.0.1:8765 --node-id node-2 --index 2 --total 3

# 查询
curl -s -X POST http://127.0.0.1:8765/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"多台电脑如何组成智能体","timeout":6}'
```

或直接 `python3 demo.py`（1 协调者 + 3 节点 + 两次查询）。

## 5. 一键加入（互联网）

先在公网服务器部署协调者（见 §7），然后每台电脑执行：

```bash
curl -fsSL https://raw.githubusercontent.com/your-org/netagent/main/install.sh | bash -s -- \
  --coordinator https://coord.example.com --token YOUR_TOKEN
```

安装脚本会：

1. 检测 Python3；
2. 下载 `node.py` / `corpus.py` 到 `~/.netagent`；
3. 写入配置与 `run.sh`（`nice -n 19`）；
4. 注册为 launchd（macOS）/ systemd --user（Linux）/ nohup；
5. 节点**只建立出站连接**，不开放入站端口。

管理：

```bash
bash install.sh --pause      # 暂停（不吃 CPU）
bash install.sh --resume     # 恢复
bash install.sh --uninstall  # 卸载
```

## 6. 不影响正常工作

- **出站 only**：节点主动连协调者，不需要公网 IP/端口映射；
- **低优先级**：`nice -n 19`，轮询间隔 0.6–1.0s，空闲才干活；
- **可暂停**：`pause` 文件存在时节点只睡眠；
- **可卸载**：一条命令删除服务与目录；
- **不跑任意代码**：任务只调用内置技能（检索/NLI），带超时与大小限制；
- **可限流**：协调者限制每节点并发与 QPS（TODO 已留接口）。

## 7. 部署协调者（公网）

```bash
# 服务器
python3 coordinator.py 8765

# Caddy 反代 + TLS（示例）
coord.example.com {
  reverse_proxy 127.0.0.1:8765
}
```

- 用 Caddy/Nginx 提供 HTTPS；
- 用 token/白名单限制加入；
- 监控 `/status`（节点数、任务数）；
- 生产环境建议加 Redis/Postgres 持久化与审计。

## 8. 安全与隐私

- **传输**：HTTPS（Caddy/Nginx）；
- **认证**：`--token`（当前原型透传，生产需在 coordinator 校验）；
- **数据最小化**：节点只回任务所需片段/分数，不回传原始文件；
- **沙箱**：技能在本地进程内，限制输入大小/超时；不执行任意脚本；
- **审计**：记录 task_id、node_id、耗时、分数；
- **退出**：随时 pause/uninstall。

## 9. 技能扩展

在 `node.py` 中替换 `Node` 的本地技能：

```python
def handle(self, query):
    # 1) 本地检索
    # 2) 本地 NLI/验证
    # 3) 返回 {"answer":..., "score":..., "evidence":[...]}
```

建议技能：`retrieval`、`nli`、`qa`、`tool`（计算/转换）。
协调者按 `skills` 路由；节点只声明自己会什么。

## 10. API

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/register` | 节点注册 |
| POST | `/heartbeat` | 心跳 |
| GET | `/task?node_id=` | 拉取任务 |
| POST | `/result` | 上报结果 |
| POST | `/query` | 提交查询并聚合 |
| GET | `/status` | 节点/任务状态 |

## 11. 路线图

- [x] 本机多进程原型（协调者 + 3 节点）
- [x] 一键安装/暂停/卸载
- [ ] token 校验 + TLS 强制
- [ ] 技能插件化（检索/NLI/QA）
- [ ] 路由学习（bandit）+ 信誉分
- [ ] quorum/超时/重试/故障注入
- [ ] LAN 3–5 台真机联调
- [ ] 公网小规模试点（10–50 节点）

## 12. 许可证

MIT。见 `LICENSE`。

---

## 13. v2 更新（鉴权 / 技能 / 容错 / 信誉）

### 13.1 token 鉴权

协调者带 token 启动：

```bash
python3 coordinator.py 8765 secret
```

节点/客户端需带 `X-Auth-Token: secret`；错 token 返回 401，节点不会注册。

### 13.2 技能插件

`skills.py` 提供：

- `retrieval`：本地分片关键词检索；
- `echo`：连通性测试。

节点用 `--skill retrieval` 声明；协调者按 skill 路由，只把任务分给会该技能的节点。

### 13.3 quorum 与故障容错

- 查询可指定 `quorum`（默认 3）；
- 节点掉线/超时：协调者记录 `fail`，按剩余节点降级；
- 测试：`python3 test_system.py`（错 token、节点掉线、quorum 降级）。

### 13.4 信誉与指标

`GET /metrics`：

```json
{"nodes":2,"tasks":2,"results":3,"ok":3,"fail":0,"avg_score":0.42}
```

`/status` 返回每节点 `skills/ok/fail`，用于后续路由学习。

### 13.5 测试结果

```bash
$ python3 test_system.py
nodes after bad-token attempt: ['good-1', 'good-0']
wrong token query -> 401
normal results: 2
after one node down, results: 1
ALL TESTS PASSED
```
