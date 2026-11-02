# 账号与一键发布

我无法替你注册 HN/Reddit/X/知乎/V2EX：它们需要邮箱/手机验证、CAPTCHA，自动注册和批量发帖违反平台规则。

下面两个平台支持 API，正常注册一次后即可由 GitHub Action 自动发布。

## Bluesky（推荐，5 分钟）

1. 打开 https://bsky.app/ 用邮箱注册；
2. Settings → App Passwords → 新建一个；
3. 在 GitHub 仓库 Settings → Secrets and variables → Actions 添加：
   - `BLUESKY_HANDLE`（例如 `xxx.bsky.social`）
   - `BLUESKY_APP_PASSWORD`（应用密码，不是登录密码）
4. Actions → **Announce** → Run workflow。

本地预览：

```bash
python3 scripts/announce_bluesky.py --dry-run
python3 scripts/announce_bluesky.py   # 需要环境变量
```

## Dev.to（用 GitHub 登录）

1. 打开 https://dev.to/enter ，选择 **Sign in with GitHub**；
2. Settings → Extensions → **DEV Community API Keys** → 生成；
3. 添加 secret `DEVTO_API_KEY`；
4. Actions → **Announce** → Run workflow。

本地预览：

```bash
python3 scripts/announce_devto.py --dry-run
python3 scripts/announce_devto.py
```

## HN / Reddit / X / 知乎 / V2EX

这些没有可用的无账号 API，必须手动：

- Hacker News：https://news.ycombinator.com/submit
- Reddit：https://www.reddit.com/submit
- X：https://x.com/intent/post?text=OpenNetAgent%20%E2%80%94%20a%20network%20agent%20that%20cites%20real%20sources&url=https%3A%2F%2Ftinyurl.com%2F2bfybazp
- V2EX：https://www.v2ex.com/new
- 知乎：https://zhuanlan.zhihu.com/write

文案在 `promo/LAUNCH.md`，复制即可。
