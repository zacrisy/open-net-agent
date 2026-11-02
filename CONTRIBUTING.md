# Contributing

Thanks for helping build a network-native agent.

## Ways to contribute

- **Run a node** — one command, low impact, pause/uninstall anytime.
- **Add a skill plugin** — `plugins/<name>/manifest.json` + `handler.py`.
- **Improve routing / quorum / fault tolerance**.
- **Write docs / translations / client SDKs** (Go, Rust, Node).
- **Report bugs** with logs and reproduction steps.

## Dev setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 demo.py            # coordinator + 3 nodes
python3 test_system.py     # auth, fault injection, quorum
python3 test_audit.py
python3 test_bandit.py
```

NLI skill needs optional deps:

```bash
pip install -r requirements-nli.txt
TRANSFORMERS_OFFLINE=1 python3 -c "from skills import SKILLS; print(SKILLS['nli']('a || a', {}))"
```

## Plugin contract

`plugins/foo/manifest.json`:

```json
{"name":"foo","version":"1.0.0","entry":"handler.py","func":"handle","sha256":"<sha256 of handler.py>","desc":"..."}
```

`handler.py`:

```python
def handle(query, ctx):
    return {"answer": ..., "score": 0.0, "evidence": [...]}
```

Loader verifies `sha256`; mismatch is skipped.

## PR checklist

- [ ] `python -m py_compile` passes
- [ ] `test_system.py` passes
- [ ] new behavior documented
- [ ] no secrets/tokens in code
