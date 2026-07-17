#!/bin/bash
# ============================================================================
# deploy_vm.sh — First-time setup on the VM.
# Run from inside the cloned repo:
#   bash infra/deploy_vm.sh
# ============================================================================
set -e

# Auto-detect repo root — wherever this script lives
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INFRA_DIR="$REPO_DIR/infra"

echo "Repo root: $REPO_DIR"

# ── Step 1: Create .env files (only if they don't exist) ──────────────────
echo ""
echo "===== [1/7] Create .env files ====="

if [ ! -f "$REPO_DIR/concur-stub/.env" ]; then
  cat > "$REPO_DIR/concur-stub/.env" <<'EOF'
PORT=8001
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000,http://localhost:4000,http://169.60.30.246
EOF
  echo "  Created concur-stub/.env"
fi

if [ ! -f "$REPO_DIR/layer2-middleware/.env" ]; then
  cat > "$REPO_DIR/layer2-middleware/.env" <<'EOF'
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
LAYER3_BASE_URL=http://localhost:8001
LAYER3_API_KEY=
DRY_RUN=false
PORT=8000
LOG_LEVEL=info
EOF
  echo "  Created layer2-middleware/.env"
fi

if [ ! -f "$REPO_DIR/expense-copilot/bff/.env" ]; then
  cat > "$REPO_DIR/expense-copilot/bff/.env" <<'EOF'
PORT=4000
LAYER2_BASE_URL=http://localhost:8000
LAYER3_BASE_URL=http://localhost:8001
CORS_ORIGIN=http://169.60.30.246
SESSION_SECRET=concur-copilot-session-secret-2026
EOF
  echo "  Created bff/.env"
fi

# ── Step 2: Python venvs + deps ───────────────────────────────────────────
echo ""
echo "===== [2/7] Python venvs + deps ====="

if [ ! -d "$REPO_DIR/concur-stub/.venv" ]; then
  python3 -m venv "$REPO_DIR/concur-stub/.venv"
  echo "  Created concur-stub/.venv"
fi
"$REPO_DIR/concur-stub/.venv/bin/pip" install -q --upgrade pip
"$REPO_DIR/concur-stub/.venv/bin/pip" install -q -r "$REPO_DIR/concur-stub/requirements.txt"
echo "  concur-stub deps installed."

if [ ! -d "$REPO_DIR/layer2-middleware/.venv" ]; then
  python3 -m venv "$REPO_DIR/layer2-middleware/.venv"
  echo "  Created layer2-middleware/.venv"
fi
"$REPO_DIR/layer2-middleware/.venv/bin/pip" install -q --upgrade pip
"$REPO_DIR/layer2-middleware/.venv/bin/pip" install -q -r "$REPO_DIR/layer2-middleware/requirements.txt"
echo "  layer2-middleware deps installed."

# ── Step 3: Node deps ─────────────────────────────────────────────────────
echo ""
echo "===== [3/7] Node deps — BFF ====="
cd "$REPO_DIR/expense-copilot/bff" && npm install --omit=dev --silent
echo "  BFF deps installed."

# ── Step 4: Build React frontend ──────────────────────────────────────────
echo ""
echo "===== [4/7] Build React frontend ====="
cd "$REPO_DIR/expense-copilot/frontend"
npm install --silent
REACT_APP_API_URL=http://169.60.30.246/api npm run build
echo "  React build complete."

# ── Step 5: Install systemd services ─────────────────────────────────────
echo ""
echo "===== [5/7] Install systemd services ====="

# Rewrite service files with actual REPO_DIR (replaces the hardcoded /home/itzuser path)
for svc in concur-stub layer2 bff; do
  sed "s|/home/itzuser/concur-from-github|$REPO_DIR|g" \
    "$INFRA_DIR/${svc}.service" \
    | sudo tee "/etc/systemd/system/${svc}.service" > /dev/null
  echo "  Installed ${svc}.service"
done

sudo systemctl daemon-reload
sudo systemctl enable concur-stub layer2 bff
echo "  Services enabled."

# ── Step 6: Install nginx config ──────────────────────────────────────────
echo ""
echo "===== [6/7] Install nginx config ====="
sed "s|/home/itzuser/concur-from-github|$REPO_DIR|g" \
  "$INFRA_DIR/concur-project.nginx.conf" \
  | sudo tee /etc/nginx/conf.d/concur-project.conf > /dev/null
sudo nginx -t && echo "  Nginx config OK."

# ── Step 7: Start services ────────────────────────────────────────────────
echo ""
echo "===== [7/7] Start services ====="
sudo systemctl restart concur-stub && echo "  concur-stub started." && sleep 3
sudo systemctl restart layer2      && echo "  layer2 started."      && sleep 3
sudo systemctl restart bff         && echo "  bff started."
sudo systemctl reload nginx        && echo "  nginx reloaded."

echo ""
echo "===== Health checks ====="
sleep 5
echo -n "  Layer 3 (8001): "
curl -sf http://localhost:8001/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "NOT READY — run: sudo journalctl -u concur-stub -n 40"
echo -n "  Layer 2 (8000): "
curl -sf http://localhost:8000/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ok'))" 2>/dev/null || echo "NOT READY — run: sudo journalctl -u layer2 -n 40"
echo -n "  BFF    (4000): "
curl -sf http://localhost:4000/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "NOT READY — run: sudo journalctl -u bff -n 40"

echo ""
echo "✅  Setup complete.  Visit: http://169.60.30.246"
