# Join a node

```bash
curl -fsSL https://7f0d2ca7bbc474.lhr.life/install.sh | bash -s -- \
  --coordinator https://7f0d2ca7bbc474.lhr.life --token <YOUR_TOKEN>
```

## What it does

1. checks python3;
2. downloads `node.py`, `corpus.py`, `skills.py` from the coordinator;
3. writes `~/.netagent/run.sh` with `nice -n 19`;
4. installs launchd (macOS) / systemd --user (Linux) / nohup.

## Control

```bash
bash install.sh --pause
bash install.sh --resume
bash install.sh --uninstall
```

## Auto provisioning

安装脚本会运行 `provision.py`：

- 检测内存/磁盘，选择 `lite` / `auto` / `full`；
- 从协调者拉取 15 条 starter 记忆到 `~/.netagent/data/docs.json`；
- 默认 `lite` 不需要任何模型，只开 retrieval/echo；
- 有 `transformers`+`torch` 且内存 ≥4GB 时自动加 `nli`；
- 可选 `--data-dir ~/Documents` 把自己的文档接入本地记忆。

## Impact

- outbound only, no inbound ports;
- poll/WS with backoff;
- pause = no CPU;
- uninstall removes service + directory.
