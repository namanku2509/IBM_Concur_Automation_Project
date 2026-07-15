# IBM TechZone Deployment Plan — Bulk Receipt Automation Pipeline

## Overview

IBM TechZone provides a reserved **IBM Cloud VSI (Classic)** running on IBM Cloud infrastructure.
The entire five-process stack runs on a **single VM** — identical to local dev but with a
public IP. Ollama runs as a background `systemd` service. `nginx` acts as a reverse proxy,
giving each layer a clean public sub-path or port.

**No code changes required beyond updating environment variables.** All service URLs flip
from `localhost` to the VM's public IP or internal loopback paths.

## Reserved VM — Confirmed Details

| Field | Value |
|-------|-------|
| **Public IP** | `169.60.30.246` |
| **Private IP** | `10.177.42.219` |
| **SSH Port** | `2223` (non-standard — use `-p 2223` on all SSH/SCP commands) |
| **Username** | `itzuser` |
| **Auth** | SSH key (download from reservation page) |
| **Datacenter** | `dal10` (Dallas, us-south) |
| **Open inbound ports** | 22, 80, 443, 3389, 8443 |
| **VM flavor** | 8 vCPU × 32 GB RAM |
| **Reservation ID** | `6a55f647b47bc7c7e6d43b86` |

> ⚠️ **SSH port is 2223, not 22.** Every SSH and SCP command in this plan uses `-p 2223`.

**Port assignments (unchanged from local):**
- Layer 3 (concur-stub): `8001` → proxied via nginx at `/l3/`
- Layer 2 (layer2-middleware): `8000` → proxied via nginx at `/l2/`
- BFF (expense-copilot/bff): `4000` → proxied via nginx at `/api/`
- Frontend (expense-copilot/frontend): served as static build via nginx on `80`
- Ollama: `11434` → internal only (never exposed publicly)

---

## Architecture on TechZone VM

```
PUBLIC INTERNET
      │  HTTPS :443  (nginx — TLS termination)
      ▼
┌─────────────────────────────────────────────────────┐
│  IBM TechZone VSI  (Ubuntu 22.04, e.g. 4vCPU/16GB) │
│                                                     │
│  nginx :80/:443                                     │
│    /          → static frontend build (port 3000 build) │
│    /api/      → BFF :4000                           │
│    /l2/       → Layer 2 :8000                       │
│    /l3/       → Layer 3 :8001                       │
│                                                     │
│  BFF           :4000  (Node.js / Express)           │
│  Layer 2       :8000  (FastAPI uvicorn)             │
│  Layer 3       :8001  (FastAPI uvicorn)             │
│  Ollama        :11434 (internal only)               │
│                                                     │
│  SQLite DB     ~/concur-stub/concur_stub.db         │
└─────────────────────────────────────────────────────┘
```

---

## Sub-Task D1 — Provision the TechZone VSI

**Status:** [x] done

### Confirmed
VM has been reserved. All details are recorded in the **Reserved VM** table above.

### First SSH Connection
Verify access with:
```bash
ssh -i <your-key.pem> -p 2223 itzuser@169.60.30.246
```

OS confirmed: **Red Hat Enterprise Linux 8.9 (Ootpa)**
- Package manager: `dnf` (not `apt`)
- Sudo: full root access confirmed
- All D2 install commands use `dnf`

---

## Sub-Task D2 — Install System Dependencies on the VM

**Status:** [ ] pending

### Intent
Install Python 3.11, Node.js 18, poppler (required by Layer 2's pdf2image), nginx,
and Ollama on the VM. These are the only system-level dependencies the stack needs.

### Expected Outcomes
- `python3.11`, `pip`, `node` (v18+), `npm`, `nginx`, and `ollama` all available on PATH.
- `poppler-utils` installed (required by `pdf2image` in Layer 2).
- `llama3.2:3b` model pulled and ready.

### Todo List
1. Update apt and install base packages:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3.11 python3.11-venv python3-pip \
       poppler-utils nginx git curl build-essential
   ```
2. Install Node.js 18 via NodeSource:
   ```bash
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt install -y nodejs
   node --version   # should print v18.x.x
   ```
3. Install Ollama (official Linux installer — single command):
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
4. Start Ollama as a background systemd service and pull the model:
   ```bash
   sudo systemctl enable ollama
   sudo systemctl start ollama
   ollama pull llama3.2:3b   # downloads ~2GB, takes a few minutes
   ollama list               # confirm model appears
   ```
5. Verify all versions:
   ```bash
   python3.11 --version
   node --version
   npm --version
   nginx -v
   ollama --version
   ```

### Relevant Context
- Ollama's Linux installer registers a `systemd` service automatically — it will restart
  on reboot without any extra configuration.
- `poppler-utils` is the Linux equivalent of `brew install poppler` from
  [`layer2-middleware/requirements.txt`](layer2-middleware/requirements.txt:4).
- Layer 2 uses `llama3.2:3b` set in
  [`layer2-middleware/.env.example`](layer2-middleware/.env.example:7).

---

## Sub-Task D3 — Clone the Repository and Install Dependencies

**Status:** [ ] pending

### Intent
Get the project code onto the VM and install Python + Node dependencies for all three
services. This mirrors running `pip install` and `npm install` on local dev.

### Expected Outcomes
- Project code present at `~/concur-project/` on the VM.
- Python virtual environments created and dependencies installed for Layer 2 and Layer 3.
- Node modules installed for the BFF.
- Frontend production build generated (`npm run build`).

### Todo List
1. Copy the project folder from your Mac to the VM:
   ```bash
   # Run this on your Mac — note -P 2223 (uppercase P for scp port)
   scp -r -P 2223 -i <your-key.pem> "/Users/namankumar/Desktop/Concur Project" \
       itzuser@169.60.30.246:~/concur-project
   ```
2. Install Layer 3 dependencies:
   ```bash
   cd ~/concur-project/concur-stub
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   deactivate
   ```
3. Install Layer 2 dependencies:
   ```bash
   cd ~/concur-project/layer2-middleware
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   deactivate
   ```
4. Install BFF dependencies:
   ```bash
   cd ~/concur-project/expense-copilot/bff
   npm install
   ```
5. Build the React frontend as static files:
   ```bash
   cd ~/concur-project/expense-copilot/frontend
   npm install
   REACT_APP_API_URL=http://169.60.30.246/api npm run build
   ```
   This produces a `build/` folder that nginx will serve as static HTML.

### Relevant Context
- `scp` is the simplest option for a TechZone demo — no GitHub account needed.
- The `REACT_APP_API_URL` env var must point to the VM's public IP so the browser
  sends BFF calls to the right address (not `localhost`).
- Docling (in Layer 2 requirements) downloads ML model weights on first use (~500MB).
  Run a test call after startup to warm the cache before any demo.

---

## Sub-Task D4 — Configure Environment Variables for Cloud

**Status:** [ ] pending

### Intent
The only code-level change needed for TechZone deployment is updating environment
variables — `localhost` URLs become the VM's loopback address (services communicate
internally via `127.0.0.1`) and the BFF CORS origin becomes the VM's public IP.

### Expected Outcomes
- Each service has a `.env` file with correct URLs for the VM environment.
- All inter-service calls use `127.0.0.1` (loopback) — services are on the same VM.
- BFF CORS and session cookie settings are updated for the public-facing URL.

### Todo List
1. Create **`concur-stub/.env`** (copy from example, no changes needed — defaults are correct):
   ```bash
   cd ~/concur-project/concur-stub
   cp .env.example .env
   # DB_PATH, API_KEY etc. are all fine as defaults
   ```
2. Create **`layer2-middleware/.env`**:
   ```bash
   cd ~/concur-project/layer2-middleware
   cat > .env << 'EOF'
   OLLAMA_HOST=http://127.0.0.1:11434
   OLLAMA_MODEL=llama3.2:3b
   LAYER3_BASE_URL=http://127.0.0.1:8001
   LAYER3_API_KEY=concur-stub-dev-key
   DRY_RUN=false
   PORT=8000
   LOG_LEVEL=info
   EOF
   ```
3. Create **`expense-copilot/bff/.env`**:
   ```bash
   cd ~/concur-project/expense-copilot/bff
   cat > .env << 'EOF'
   PORT=4000
   LAYER2_BASE_URL=http://127.0.0.1:8000
   LAYER3_BASE_URL=http://127.0.0.1:8001
   LAYER3_API_KEY=concur-stub-dev-key
   SESSION_SECRET=<generate-a-random-string>
   FRONTEND_ORIGIN=http://169.60.30.246
   EOF
   ```
4. Update **`expense-copilot/bff/server.js`** CORS origin to read from env:
   ```javascript
   // Change line 10 from:
   app.use(cors({ origin: 'http://localhost:3000', credentials: true }));
   // To:
   app.use(cors({
     origin: process.env.FRONTEND_ORIGIN || 'http://localhost:3000',
     credentials: true
   }));
   ```
   This is the **only code change** required for cloud deployment.

### Relevant Context
- All services are on the same VM — inter-service calls use `127.0.0.1`, not the
  public IP. This avoids routing traffic through the public internet unnecessarily.
- `FRONTEND_ORIGIN` in the BFF `.env` must exactly match the URL users open in their
  browser (including protocol and port). For HTTP-only: `http://169.60.30.246`.
- The session cookie `secure: false` in `server.js` is correct for HTTP. If you add
  HTTPS later, change to `secure: true`.

---

## Sub-Task D5 — Create systemd Services for Auto-Start

**Status:** [ ] pending

### Intent
Register Layer 2, Layer 3, and the BFF as `systemd` services so they start automatically
on boot and restart if they crash. This replaces manually running `uvicorn` in terminal
tabs.

### Expected Outcomes
- `concur-stub.service`, `layer2.service`, and `bff.service` registered and enabled.
- All three services start on VM boot without manual intervention.
- `systemctl status <service>` shows `active (running)` for each.

### Todo List
1. Create **`/etc/systemd/system/concur-stub.service`**:
   ```ini
   [Unit]
   Description=SAP Concur Stub (Layer 3)
   After=network.target

   [Service]
   User=itzuser
   WorkingDirectory=/home/ubuntu/concur-project/concur-stub
   EnvironmentFile=/home/ubuntu/concur-project/concur-stub/.env
   ExecStart=/home/ubuntu/concur-project/concur-stub/.venv/bin/uvicorn \
       main:app --host 127.0.0.1 --port 8001
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
2. Create **`/etc/systemd/system/layer2.service`**:
   ```ini
   [Unit]
   Description=AI Middleware (Layer 2)
   After=network.target ollama.service

   [Service]
   User=itzuser
   WorkingDirectory=/home/ubuntu/concur-project/layer2-middleware
   EnvironmentFile=/home/ubuntu/concur-project/layer2-middleware/.env
   ExecStart=/home/ubuntu/concur-project/layer2-middleware/.venv/bin/uvicorn \
       main:app --host 127.0.0.1 --port 8000
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
3. Create **`/etc/systemd/system/bff.service`**:
   ```ini
   [Unit]
   Description=Expense Copilot BFF (Layer 1)
   After=network.target

   [Service]
   User=itzuser
   WorkingDirectory=/home/ubuntu/concur-project/expense-copilot/bff
   EnvironmentFile=/home/ubuntu/concur-project/expense-copilot/bff/.env
   ExecStart=/usr/bin/node server.js
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
4. Enable and start all three:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable concur-stub layer2 bff
   sudo systemctl start concur-stub layer2 bff
   ```
5. Verify:
   ```bash
   sudo systemctl status concur-stub
   sudo systemctl status layer2
   sudo systemctl status bff
   ```

### Relevant Context
- `After=ollama.service` in `layer2.service` ensures Ollama is up before Layer 2 tries
  to connect to it.
- Services bind to `127.0.0.1` (not `0.0.0.0`) — nginx proxies inbound public traffic
  to them. This follows the security rule of never binding to all interfaces.
- Logs are viewable with `journalctl -u layer2 -f` (follow mode).

---

## Sub-Task D6 — Configure nginx as Reverse Proxy + Static File Server

**Status:** [ ] pending

### Intent
nginx acts as the single public entry point on port 80. It serves the React static
build directly, proxies `/api/` to the BFF, and optionally exposes Layer 2 and Layer 3
health endpoints. This means users only need to know one IP address.

### Expected Outcomes
- `http://169.60.30.246/` serves the React frontend.
- `http://169.60.30.246/api/` proxies to the BFF on port 4000.
- All five services are reachable from a browser with a single VM IP.

### Todo List
1. Create **`/etc/nginx/sites-available/concur-project`**:
   ```nginx
   server {
       listen 80;
       server_name _;

       # ── React static build ───────────────────────────────────────────
       root /home/ubuntu/concur-project/expense-copilot/frontend/build;
       index index.html;

       location / {
           try_files $uri $uri/ /index.html;
       }

       # ── BFF API proxy ────────────────────────────────────────────────
       location /api/ {
           proxy_pass         http://127.0.0.1:4000;
           proxy_http_version 1.1;
           proxy_set_header   Host $host;
           proxy_set_header   X-Real-IP $remote_addr;
           proxy_read_timeout 300s;   # 5 min — covers Ollama processing time
           proxy_send_timeout 300s;
       }

       # ── Layer 2 health (optional — useful for demo) ──────────────────
       location /l2/ {
           proxy_pass http://127.0.0.1:8000/;
           proxy_http_version 1.1;
           proxy_set_header Host $host;
       }

       # ── Layer 3 health (optional — useful for demo) ──────────────────
       location /l3/ {
           proxy_pass http://127.0.0.1:8001/;
           proxy_http_version 1.1;
           proxy_set_header Host $host;
       }
   }
   ```
2. Enable the site and remove the default nginx page:
   ```bash
   sudo ln -s /etc/nginx/sites-available/concur-project \
       /etc/nginx/sites-enabled/concur-project
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t          # test config — must say "syntax is ok"
   sudo systemctl reload nginx
   ```
3. Verify from your local machine:
   ```bash
   curl http://169.60.30.246/health          # nginx serves 404 (expected, no /health root)
   curl http://169.60.30.246/api/health      # BFF health → {"service":"BFF Server","status":"ok"}
   curl http://169.60.30.246/l3/health       # Layer 3 → {"status":"ok","service":"SAP Concur Stub"}
   curl http://169.60.30.246/l2/health       # Layer 2 → {"status":"ok"}
   ```
4. Open `http://169.60.30.246` in a browser — the React app should load.

### Relevant Context
- `proxy_read_timeout 300s` is critical — without it nginx will kill Ollama processing
  requests (which can take 60–120s) with a 60s default timeout.
- The `try_files ... /index.html` fallback is required for React Router to work — without
  it, refreshing any page other than `/` returns a 404.
- `server_name _;` matches any hostname/IP — correct for a demo with no registered domain.

---

## Key Differences: Local vs TechZone

| Concern | Local (Mac) | TechZone VM |
|---------|-------------|-------------|
| Service URLs | `localhost:XXXX` | `127.0.0.1:XXXX` (same VM) |
| Frontend served by | `react-scripts start` | nginx (static build) |
| Public entry point | 4 separate ports | Single IP port 80 via nginx |
| Process management | Terminal tabs | systemd services |
| Ollama | `ollama serve` in terminal | systemd service (auto-start) |
| CORS origin | `http://localhost:3000` | `http://169.60.30.246` |
| Session cookie | `secure: false` | `secure: false` (HTTP-only demo) |
| SQLite DB | Local file | VM file (persists until VM deleted) |

---

## Post-Deployment Health Check

After all sub-tasks complete, run this sequence to validate:

```bash
# On the VM
sudo systemctl status ollama concur-stub layer2 bff   # all should be active

# From your laptop
curl http://169.60.30.246/api/health
# → {"service":"BFF Server","status":"ok"}

curl http://169.60.30.246/l3/health
# → {"status":"ok","service":"SAP Concur Stub","version":"1.0.0"}

curl http://169.60.30.246/l2/health
# → {"status":"ok"}

# Open in browser
open http://169.60.30.246
# → React app loads, corporate card transactions auto-fetch
```

---

## Important Notes

- **TechZone reservation duration**: Default is 2 days. Extend it before your demo date
  from the TechZone portal.
- **SQLite persistence**: The database file lives at `~/concur-project/concur-stub/concur_stub.db`.
  It persists as long as the VM exists. If you want a clean state, delete the file and
  restart `concur-stub` — it re-seeds automatically.
- **Ollama first-run warmup**: The first receipt processed after a fresh Ollama start
  takes 20–40s longer while the model loads into memory. Run one test upload before
  any demo to warm it up.
- **VM size and Ollama**: `llama3.2:3b` requires ~2.5GB RAM for the model weights. A 16GB
  VM has comfortable headroom. Do not use a 4GB VM.
- **No HTTPS for demo**: TechZone VMs have a plain IP — getting a TLS certificate requires
  a domain name. HTTP-only is fine for an internal demo. If you need HTTPS, request a
  TechZone environment with a pre-assigned hostname and use Let's Encrypt certbot.
