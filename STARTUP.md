# Startup Guide — IBM Expense Claims Copilot

## Prerequisites (already satisfied on this machine)

| Requirement | Status |
|---|---|
| Python 3.12 | ✅ `/opt/homebrew/bin/python3.12` |
| Node.js 26 | ✅ |
| Ollama 0.32 + llama3.2:3b | ✅ model pulled |
| poppler (pdf2image) | ✅ `brew install poppler` done |
| Python venvs + pip deps | ✅ `concur-stub/venv` and `layer2-middleware/venv` created |
| Node modules | ✅ `bff/node_modules` and `frontend/node_modules` created |
| `.env` files | ✅ copied from `.env.example` in each service |

---

## Port Map

| Service | Port | URL |
|---|---|---|
| Layer 3 — SAP Concur Stub | **8001** | http://localhost:8001 |
| Layer 2 — AI Middleware | **8000** | http://localhost:8000 |
| BFF — Node/Express | **4000** | http://localhost:4000 |
| Frontend — React | **3000** | http://localhost:3000 |

---

## Startup Order — open 5 terminals

### Terminal 1 — Ollama (if not already running)

```bash
ollama serve
```

> Skip if `ollama serve` is already running in the background.
> Check: `curl http://localhost:11434/api/tags`

---

### Terminal 2 — Layer 3: SAP Concur Stub (port 8001)

```bash
cd "IBM_Concur_Automation_Project/concur-stub"
venv/bin/uvicorn main:app --port 8001 --reload
```

Health check: http://localhost:8001/health  
Swagger UI: http://localhost:8001/docs

---

### Terminal 3 — Layer 2: AI Middleware (port 8000)

```bash
cd "IBM_Concur_Automation_Project/layer2-middleware"
venv/bin/uvicorn main:app --port 8000 --reload
```

Health check: http://localhost:8000/health  
Swagger UI: http://localhost:8000/docs

---

### Terminal 4 — BFF: Node/Express (port 4000)

```bash
cd "IBM_Concur_Automation_Project/expense-copilot/bff"
npm start
```

Health check: http://localhost:4000/health

---

### Terminal 5 — Frontend: React (port 3000)

```bash
cd "IBM_Concur_Automation_Project/expense-copilot/frontend"
npm start
```

Opens automatically at http://localhost:3000

---

## Smoke Test (Happy Path)

1. Open http://localhost:3000
2. Fill the form: report name, business purpose, policy = **STANDARD**, category = **CUSTOMER_CLIENT_RELATED_TRAVEL**
3. Click **Create Expense Report** → navigates to the report folder page
4. Transactions table auto-loads 6 corporate card entries
5. Upload one or more PDF receipts → Layer 2 runs OCR + Ollama categorisation (30–90 s)
6. Review processed expenses table
7. Click **Submit Report** → Layer 3 transitions status to SUBMITTED

---

## Re-seeding the Database

If you want a clean database:

```bash
cd "IBM_Concur_Automation_Project/concur-stub"
rm -f concur_stub.db
# then restart Terminal 2 — seed runs automatically on startup
```
