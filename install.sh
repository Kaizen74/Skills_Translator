#!/bin/bash
# SkillBridge one-shot installer for Ubuntu (Beelink GTR9 Pro).
# Copy-paste friendly: run it once from the project folder; it explains
# what it is doing and how to check that each step worked.
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8788

echo ""
echo "=== SkillBridge installer ==="
echo "This will set up SkillBridge in: $APP_DIR"
echo ""

# --- 1. Python check --------------------------------------------------------
echo "[1/6] Checking Python..."
if ! command -v python3 >/dev/null; then
  echo "❌ Python 3 is not installed. Run:  sudo apt install python3 python3-venv"
  exit 1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "❌ The Python 'venv' module is missing. Run:  sudo apt install python3-venv"
  echo "   Then run this installer again."
  exit 1
fi
echo "   ✅ $(python3 --version) found."

# --- 2. Private Python environment + dependencies ---------------------------
echo "[2/6] Installing SkillBridge's own Python packages (one-time download)..."
if [ ! -d "$APP_DIR/.venv" ]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
echo "   ✅ Packages installed."

# --- 3. SkillBridge folders --------------------------------------------------
echo "[3/6] Creating the SkillBridge folders in your home directory..."
mkdir -p "$HOME/SkillBridge/inbox" "$HOME/SkillBridge/library/prompt-packs" \
         "$HOME/SkillBridge/work" "$HOME/SkillBridge/logs"
echo "   ✅ Folders ready: ~/SkillBridge/{inbox, library/prompt-packs, work, logs}"

# --- 4. Quick self-test (no model needed) ------------------------------------
echo "[4/6] Running the app's self-checks (takes under a minute)..."
if (cd "$APP_DIR" && SKILLBRIDGE_PY="$APP_DIR/.venv/bin/python" ./run_checks.sh > /tmp/skillbridge_checks.log 2>&1); then
  echo "   ✅ All self-checks passed."
else
  echo "❌ The self-checks failed. The log is in /tmp/skillbridge_checks.log"
  echo "   Please share that file when asking for help."
  exit 1
fi

# --- 5. Start-on-boot service -------------------------------------------------
echo "[5/6] Installing SkillBridge as a background service that starts on boot..."
mkdir -p "$HOME/.config/systemd/user"
sed "s|__APP_DIR__|$APP_DIR|g" "$APP_DIR/systemd/skillbridge.service" \
  > "$HOME/.config/systemd/user/skillbridge.service"
systemctl --user daemon-reload
systemctl --user enable --now skillbridge.service
# Lingering lets the service run even before you log in after a reboot.
loginctl enable-linger "$USER" 2>/dev/null || true
echo "   ✅ Service installed and started."

# --- 6. Success check ----------------------------------------------------------
echo "[6/6] Checking that SkillBridge is answering..."
sleep 3
if curl -s "http://127.0.0.1:$PORT/api/health" | grep -q "ollama_ok"; then
  echo "   ✅ SkillBridge is running."
else
  echo "⚠️  SkillBridge did not answer yet. Wait 10 seconds, then open the address below."
  echo "   If it still fails, run:  systemctl --user status skillbridge"
fi

TSNAME=$(command -v tailscale >/dev/null && tailscale status --self --peers=false 2>/dev/null | awk '{print $2; exit}' || true)
echo ""
echo "=== Done! ==="
echo "On this machine, open:      http://localhost:$PORT"
[ -n "$TSNAME" ] && echo "From your laptop (Tailscale): http://$TSNAME:$PORT"
echo "You should see the SkillBridge home screen with a green Health section."
echo ""
echo "Next step: open Settings in the app and press 'Test connection to Ollama'."
