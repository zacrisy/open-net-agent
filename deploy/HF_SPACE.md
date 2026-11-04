# Deploy OpenNetBrain to Hugging Face Spaces (24/7, free CPU)

1. Create a free account: https://huggingface.co/join
2. Create a **write** token: https://huggingface.co/settings/tokens
3. Run（SPACE 可省略，默认 `你的用户名/open-net-brain`）：

```bash
cd network_agent
HF_TOKEN=hf_xxx bash deploy/hf_space.sh
```

The Space builds the root `Dockerfile` and serves the full API + brain.html on:

`https://YOUR_USERNAME-open-net-brain.hf.space`

Health check: `/health`.

After it is live, set `brain.html` `PRIMARY` to the Space URL so Pages uses the full API instead of the quick tunnel.

Note: the Space free CPU may sleep after long inactivity; a paid persistent Space avoids that. The app's `BRAIN_AUTO=1` heartbeat runs learning/evolution inside the container.
