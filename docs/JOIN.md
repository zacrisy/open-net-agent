# Join a node

```bash
curl -fsSL https://76ee4c4f2339b6.lhr.life/install.sh | bash -s -- \
  --coordinator https://76ee4c4f2339b6.lhr.life --token <YOUR_TOKEN>
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

## Impact

- outbound only, no inbound ports;
- poll/WS with backoff;
- pause = no CPU;
- uninstall removes service + directory.
