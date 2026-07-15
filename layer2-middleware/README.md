# Layer 2 — AI Middleware
### Expense Claims Copilot · IBM Internship Project

This is **Layer 2** of the three-layer Expense Claims Copilot system.

```
Layer 1 (watsonx Orchestrate)
        │  POST /pipeline/run
        ▼
Layer 2 — AI Middleware  ◄── YOU ARE HERE
        │  HTTP (Concur-format JSON)
        ▼
Layer 3 (SAP Concur Stub)
```

---

## What This Service Does

For every batch of PDF receipts uploaded by an employee, Layer 2 runs a 5-stage pipeline:

| Stage | What happens |
|---|---|
| **1. OCR** | Docling (IBM open-source, local) extracts structured text from each PDF — no API key, no network call |
| **2. Categorise** | Ollama `llama3.2:3b` (local LLM) classifies the receipt: `HOTEL / TAXI / FLIGHT / MEALS` |
| **3. Extract** | Ollama uses a type-specific prompt (grounded in Layer 3's DB schema) to extract structured fields |
| **4. Match** | Fuzzy-matches extracted data against corporate card transactions fetched from Layer 3 |
| **5. Submit** | Translates to Layer 3's JSON format and posts to Layer 3 endpoints |

**No IBM Cloud credentials required.** Both AI engines run entirely on your local machine.

---

## Prerequisites

### Python
- Python 3.10 or later

### Ollama — local LLM server

**macOS (no Homebrew needed):**
```bash
# Download the binary directly
mkdir -p ~/bin
curl -fsSL "https://github.com/ollama/ollama/releases/download/v0.31.2/ollama-darwin.tgz" \
  -o /tmp/ollama-darwin.tgz
tar -xzf /tmp/ollama-darwin.tgz -C ~/bin
chmod +x ~/bin/ollama
export PATH="$HOME/bin:$PATH"   # add to ~/.zshrc to persist

# Pull the model (one-time, ~2 GB)
ollama pull llama3.2:3b
```

**macOS (with Homebrew):**
```bash
brew install ollama
ollama pull llama3.2:3b
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
```

---

## Setup

```bash
# 1. Navigate to this folder
cd layer2-middleware

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure environment (defaults work out of the box)
cp .env.example .env
```

---

## Configuration

`.env` defaults work with no changes. Edit only if you need to:

```bash
# Ollama server (default port — leave as-is unless you changed it)
OLLAMA_HOST=http://localhost:11434

# LLM model — llama3.2:3b runs in < 2 GB RAM on Apple Silicon
OLLAMA_MODEL=llama3.2:3b

# Layer 3 SAP Concur Stub (update when Layer 3 team confirms their port)
LAYER3_BASE_URL=http://localhost:8001

# Set to "true" to test OCR + extraction + matching without Layer 3 running
DRY_RUN=true
```

> **Note on Layer 3 endpoints:** If Layer 3 uses different URL paths, update `LAYER3_ENDPOINTS`
> in `src/config.py`. That is the only file that ever needs to change.

---

## Start the Server

```bash
# Terminal 1 — keep Ollama running
ollama serve

# Terminal 2 — start Layer 2
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Server starts at: `http://localhost:8000`

On startup, the console shows:
```
Layer 2 — AI Middleware started
OCR engine    : Docling (local — no API key)
LLM engine    : Ollama  (local — no API key)
Ollama host   : http://localhost:11434
Ollama model  : llama3.2:3b
Ollama status : RUNNING
Layer 3 URL   : http://localhost:8001
DRY_RUN       : True
OpenAPI spec  : http://localhost:8000/openapi.json
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/pipeline/run` | Process a batch of PDF receipts — primary skill endpoint |
| `GET` | `/health` | Liveness probe |
| `GET` | `/watsonx/status` | Check Docling + Ollama readiness |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/openapi.json` | OpenAPI spec (used by watsonx Orchestrate) |

---

## Running the End-to-End Test

### Step 1 — Generate sample PDFs (one-time)
```bash
python data/generate_sample_pdfs.py
# Creates 6 PDFs in data/sample_receipts/
```

### Step 2 — Start Ollama
```bash
# In a dedicated terminal — keep it running
ollama serve
```

### Step 3 — Start Layer 2
```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Step 4 — Run the test
```bash
# DRY_RUN mode — tests full OCR + extraction + matching without Layer 3
python test_pipeline.py

# Full mode — requires Layer 3 running on port 8001
DRY_RUN=false python test_pipeline.py
```

Expected output (DRY_RUN):
```
✓ Pipeline completed successfully — 6 receipts processed
  hotel_marriott.pdf  → HOTEL   Marriott Bengaluru   INR 10530.0
  taxi_ola.pdf        → TAXI    Ola Cabs             INR 441.0
  flight_indigo.pdf   → FLIGHT  IndiGo               INR 3880.0
  meals_restaurant.pdf→ MEALS   Mainland China       INR 1851.0
  ...
```

---

## Folder Structure

```
layer2-middleware/
├── main.py                      # FastAPI entry point
├── requirements.txt
├── .env.example
├── test_pipeline.py             # End-to-end test script
│
├── src/
│   ├── config.py                # Env vars + LAYER3_ENDPOINTS path table
│   ├── routes/
│   │   ├── pipeline.py          # POST /pipeline/run
│   │   └── health.py            # GET /health, GET /watsonx/status
│   ├── services/
│   │   ├── ocr_service.py       # Stage 1: PDF → text (Docling, local)
│   │   ├── categorisation_service.py  # Stage 2: classify expense type (Ollama)
│   │   ├── extraction_service.py      # Stage 3: extract fields (Ollama)
│   │   ├── matching_service.py        # Stage 4: fuzzy match card txns
│   │   ├── schema_mapper.py           # Stage 5a: build Layer 3 payloads
│   │   ├── concur_client.py           # Stage 5b: HTTP calls to Layer 3
│   │   └── hash_service.py            # SHA-256 utility
│   ├── models/
│   │   ├── receipt_models.py    # Pipeline-internal Pydantic models
│   │   ├── concur_models.py     # Layer 3 request/response models
│   │   └── pipeline_models.py   # /pipeline/run request/response
│   └── prompts/
│       ├── categorisation_prompt.py  # Ollama categorisation prompt
│       └── extraction_prompt.py      # Ollama extraction prompts (4 types)
│
└── data/
    ├── generate_sample_pdfs.py  # Creates test PDFs with reportlab
    └── sample_receipts/         # Place PDF receipts here for testing
```

---

## Updating Layer 3 Endpoint Paths

When the Layer 3 team finalises their API, open `src/config.py` and update:

```python
LAYER3_ENDPOINTS = {
    "submit_expense":         "/expense/v4/reports/{report_id}/expenses",
    "attach_receipt":         "/expense/v4/reports/{report_id}/expenses/{expense_id}/receipts",
    "available_transactions": "/expense/v4/availableexpenses",
    "link_transaction":       "/expense/v4/transactions/{txn_id}/match",
}
```

No other file needs to change.

---

## Importing into watsonx Orchestrate

See [`docs/openapi_skill_guide.md`](docs/openapi_skill_guide.md) for step-by-step instructions
on registering `POST /pipeline/run` as a skill in your Orchestrate tenant.
