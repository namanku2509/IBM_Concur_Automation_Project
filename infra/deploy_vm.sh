#!/bin/bash
# ============================================================================
# deploy_vm.sh — Run this on the VM after git pull to set up all services
# Usage: bash infra/deploy_vm.sh
# ============================================================================
set -e

REPO_DIR="/home/itzuser/concur-from-github"
INFRA_DIR="$REPO_DIR/infra"

echo "===== Step 1: Create .env files (only if they don't exist) ====="

if [ ! -f "$REPO_DIR/concur-stub/.env" ]; then
  cat > "$REPO_DIR/concur-stub/.env" <<'EOF'
PORT=8001
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:3000,http://localhost:4000,http://169.60.30.246
EOF
  echo "Created concur-stub/.env"
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
  echo "Created layer2-middleware/.env"
fi

if [ ! -f "$REPO_DIR/expense-copilot/bff/.env" ]; then
  cat > "$REPO_DIR/expense-copilot/bff/.env" <<'EOF'
PORT=4000
LAYER2_BASE_URL=http://localhost:8000
LAYER3_BASE_URL=http://localhost:8001
CORS_ORIGIN=http://169.60.30.246
SESSION_SECRET=concur-copilot-session-secret-2026
EOF
  echo "Created bff/.env"
fi

echo "===== Step 2: Install systemd services ====="

sudo cp "$INFRA_DIR/concur-stub.service"   /etc/systemd/system/concur-stub.service
sudo cp "$INFRA_DIR/layer2.service"        /etc/systemd/system/layer2.service
sudo cp "$INFRA_DIR/bff.service"           /etc/systemd/system/bff.service

sudo systemctl daemon-reload
sudo systemctl enable concur-stub layer2 bff
echo "Systemd services installed and enabled"

echo "===== Step 3: Install nginx config ====="

sudo cp "$INFRA_DIR/concur-project.nginx.conf" /etc/nginx/conf.d/concur-project.conf
sudo nginx -t && echo "Nginx config OK"

echo "===== Step 4: Build React frontend ====="

cd "$REPO_DIR/expense-copilot/frontend"
REACT_APP_API_URL=http://169.60.30.246/api npm run build
echo "React build complete"

echo "===== Step 5: Start all services ====="

sudo systemctl restart concur-stub
sleep 3
sudo systemctl restart layer2
sleep 3
sudo systemctl restart bff
sudo systemctl reload nginx

echo ""
echo "===== Step 6: Health checks ====="

sleep 5
echo -n "Layer 3 (port 8001): "
curl -sf http://localhost:8001/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "NOT READY"

echo -n "Layer 2 (port 8000): "
curl -sf http://localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','ok'))" 2>/dev/null || echo "NOT READY"

echo -n "BFF    (port 4000): "
curl -sf http://localhost:4000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "NOT READY"

echo ""
echo "✅ Deployment complete! Visit: http://169.60.30.246"
