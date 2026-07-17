#!/bin/bash
# ============================================================================
# update_vm.sh — Pull latest code and redeploy. Run from inside the repo:
#   bash infra/update_vm.sh
# ============================================================================
set -e

# Auto-detect repo root — wherever this script lives
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
echo "Repo root: $REPO_DIR"

# ── Step 1: Pull latest code ──────────────────────────────────────────────
echo ""
echo "===== [1/6] git pull ====="
git pull origin main
echo "  Code updated."

# ── Step 2: Python deps — concur-stub ────────────────────────────────────
echo ""
echo "===== [2/6] Python deps — concur-stub ====="
"$REPO_DIR/concur-stub/.venv/bin/pip" install -q --upgrade -r "$REPO_DIR/concur-stub/requirements.txt"
echo "  concur-stub deps OK."

# ── Step 3: Python deps — layer2-middleware ───────────────────────────────
echo ""
echo "===== [3/6] Python deps — layer2-middleware ====="
"$REPO_DIR/layer2-middleware/.venv/bin/pip" install -q --upgrade -r "$REPO_DIR/layer2-middleware/requirements.txt"
echo "  layer2-middleware deps OK."

# ── Step 4: Node deps + React build ──────────────────────────────────────
echo ""
echo "===== [4/6] Node deps — BFF ====="
cd "$REPO_DIR/expense-copilot/bff" && npm install --omit=dev --silent
echo "  BFF deps OK."

echo ""
echo "===== [5/6] Build React frontend ====="
cd "$REPO_DIR/expense-copilot/frontend"
npm install --silent
REACT_APP_API_URL=http://169.60.30.246/api npm run build
echo "  React build complete."

# ── Step 5: Restart services ──────────────────────────────────────────────
echo ""
echo "===== [6/6] Restart services ====="
sudo systemctl restart concur-stub && echo "  concur-stub restarted." && sleep 3
sudo systemctl restart layer2      && echo "  layer2 restarted."      && sleep 3
sudo systemctl restart bff         && echo "  bff restarted."
sudo systemctl reload nginx        && echo "  nginx reloaded."

# ── Health checks ─────────────────────────────────────────────────────────
echo ""
echo "===== Health checks ====="
sleep 5

echo -n "  Layer 3 (8001): "
curl -sf http://localhost:8001/health \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null \
  || echo "NOT READY — check: sudo journalctl -u concur-stub -n 30"

echo -n "  Layer 2 (8000): "
curl -sf http://localhost:8000/health \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ok'))" 2>/dev/null \
  || echo "NOT READY — check: sudo journalctl -u layer2 -n 30"

echo -n "  BFF    (4000): "
curl -sf http://localhost:4000/health \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null \
  || echo "NOT READY — check: sudo journalctl -u bff -n 30"

echo ""
echo "✅  Update complete.  Visit: http://169.60.30.246"
