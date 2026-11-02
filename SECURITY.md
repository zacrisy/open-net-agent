# Security

## Reporting

Please report vulnerabilities privately to the maintainers (open a draft security
advisory on GitHub, or email the address in the repo profile). Do not open a
public issue with exploit details.

## Threat model (prototype)

- Nodes are **untrusted**; they may return wrong or malicious answers.
- Coordinator is trusted in the current design.
- Token auth is required in public deployments; rotate tokens.
- Plugins run **in-process** and are not sandboxed; only install plugins you trust.
- The demo tunnel is temporary; do not send sensitive data.

## Hardening checklist

- [ ] HTTPS/WSS (Caddy/Nginx or cloudflared)
- [ ] strong tokens + rotation
- [ ] per-IP rate limit (implemented, 120/min)
- [ ] quorum + verifier for answers
- [ ] audit log retention
- [ ] plugin sha256/version pinning
- [ ] sandbox plugins (subprocess + resource limits)
