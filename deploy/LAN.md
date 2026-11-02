# LAN 3–5 台真机部署

## 拓扑

```
机器 A（协调者） 192.168.1.10:8765
机器 B/C/D（节点） 192.168.1.11-13
```

## 机器 A：协调者

```bash
python3 coordinator.py 8765 "token1"
```

打开防火墙 8765/TCP（仅内网）。

## 机器 B/C/D：节点

```bash
curl -fsSL http://192.168.1.10:8765/install.sh -o install.sh   # 或拷贝仓库
bash install.sh --local --coordinator http://192.168.1.10:8765 --token token1 --skill retrieval
```

节点出站连接，无需开入站端口。

## 验证

```bash
curl -H "X-Auth-Token: token1" http://192.168.1.10:8765/status
curl -X POST -H "X-Auth-Token: token1" -H 'Content-Type: application/json' \
  -d '{"query":"测试","timeout":8,"quorum":3}' http://192.168.1.10:8765/query
```

## 观测

- `/metrics`：节点数、ok/fail、avg_score；
- 节点日志：`~/.netagent/node.log`；
- 建议同网段，RTT < 5ms。
