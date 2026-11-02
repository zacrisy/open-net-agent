#!/usr/bin/env bash
# OpenNetAgent 一键加入脚本
# 用法：
#   curl -fsSL https://raw.githubusercontent.com/your-org/netagent/main/install.sh | bash -s -- \
#     --coordinator https://coord.example.com --token YOUR_TOKEN
# 本地测试：bash install.sh --local --coordinator http://127.0.0.1:8765 --dir /tmp/netagent --no-service
set -euo pipefail

COORD=""; TOKEN=""; DIR="$HOME/.netagent"; INDEX=0; TOTAL=1; MODE="install"; LOCAL=0; NO_SERVICE=0; SKILL="retrieval"
REPO_RAW="${REPO_RAW:-https://raw.githubusercontent.com/your-org/netagent/main}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --coordinator) COORD="$2"; shift 2;;
    --token) TOKEN="$2"; shift 2;;
    --dir) DIR="$2"; shift 2;;
    --index) INDEX="$2"; shift 2;;
    --total) TOTAL="$2"; shift 2;;
    --skill) SKILL="$2"; shift 2;;
    --local) LOCAL=1; shift;;
    --no-service) NO_SERVICE=1; shift;;
    --uninstall) MODE="uninstall"; shift;;
    --pause) MODE="pause"; shift;;
    --resume) MODE="resume"; shift;;
    -h|--help) echo "见 README.md"; exit 0;;
    *) echo "unknown $1"; exit 1;;
  esac
done

# 暂停/恢复/卸载
if [[ "$MODE" == "pause" ]]; then mkdir -p "$DIR"; touch "$DIR/pause"; echo "paused: $DIR/pause"; exit 0; fi
if [[ "$MODE" == "resume" ]]; then rm -f "$DIR/pause"; echo "resumed"; exit 0; fi
if [[ "$MODE" == "uninstall" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    launchctl unload "$HOME/Library/LaunchAgents/com.netagent.node.plist" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/com.netagent.node.plist"
  else
    systemctl --user disable --now netagent 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/netagent.service"
  fi
  rm -rf "$DIR"; echo "uninstalled"; exit 0
fi

if [[ -z "$COORD" ]]; then echo "需要 --coordinator URL"; exit 1; fi
command -v python3 >/dev/null || { echo "需要 python3"; exit 1; }
mkdir -p "$DIR"

# 获取节点代码
if [[ "$LOCAL" == "1" ]]; then
  cp "$(cd "$(dirname "$0")" && pwd)/node.py" "$DIR/node.py"
  cp "$(cd "$(dirname "$0")" && pwd)/corpus.py" "$DIR/corpus.py"
  cp "$(cd "$(dirname "$0")" && pwd)/skills.py" "$DIR/skills.py"
else
  BASE="${COORD%/}"
  for f in node.py corpus.py skills.py; do
    curl -fsSL "$BASE/$f" -o "$DIR/$f" || curl -fsSL "$REPO_RAW/$f" -o "$DIR/$f"
  done
fi

NODE_ID="$(hostname)-$(date +%s)"
cat > "$DIR/config.json" <<EOF
{"coordinator":"$COORD","node_id":"$NODE_ID","index":$INDEX,"total":$TOTAL,"token":"$TOKEN","skill":"$SKILL"}
EOF

cat > "$DIR/run.sh" <<EOF
#!/usr/bin/env bash
cd "$DIR"
exec nice -n 19 python3 "$DIR/node.py" --coordinator "$COORD" --node-id "$NODE_ID" --index $INDEX --total $TOTAL --token "$TOKEN" --skill "$SKILL" --pause-file "$DIR/pause"
EOF
chmod +x "$DIR/run.sh"

echo "installed to $DIR (node $NODE_ID)"

if [[ "$NO_SERVICE" == "1" ]]; then
  echo "no-service: run $DIR/run.sh"; exit 0
fi

if [[ "$(uname)" == "Darwin" ]]; then
  PLIST="$HOME/Library/LaunchAgents/com.netagent.node.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.netagent.node</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>$DIR/run.sh</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>Nice</key><integer>19</integer>
<key>StandardOutPath</key><string>$DIR/node.log</string>
<key>StandardErrorPath</key><string>$DIR/node.log</string>
</dict></plist>
EOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "launchd service loaded"
else
  if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
    mkdir -p "$HOME/.config/systemd/user"
    cat > "$HOME/.config/systemd/user/netagent.service" <<EOF
[Unit]
Description=OpenNetAgent node
[Service]
ExecStart=/bin/bash $DIR/run.sh
Restart=always
Nice=19
[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable --now netagent
    echo "systemd user service enabled"
  else
    nohup "$DIR/run.sh" > "$DIR/node.log" 2>&1 &
    echo "started with nohup (pid $!)"
  fi
fi
