# Importing Layer 2 as a watsonx Orchestrate Skill

This guide walks through registering `POST /pipeline/run` as a skill
in your watsonx Orchestrate tenant so Layer 1 can invoke it naturally.

---

## Prerequisites

- Layer 2 server is running and **publicly reachable** from Orchestrate.
  - For local development, use [ngrok](https://ngrok.com/) to expose your local port:
    ```bash
    ngrok http 8000
    # Copy the https URL, e.g. https://abc123.ngrok-free.app
    ```
- You have access to a watsonx Orchestrate tenant (IBM Cloud).

---

## Step 1 — Start Layer 2

```bash
cd layer2-middleware
uvicorn main:app --reload --port 8000
```

Verify the OpenAPI spec is available:
```
http://localhost:8000/openapi.json
```

---

## Step 2 — Import the Skill into Orchestrate

1. Open your **watsonx Orchestrate** tenant at `https://dl.watson-orchestrate.ibm.com`
2. In the left sidebar, click **Skills** → **Add skills**
3. Select **Import from API**
4. Choose **OpenAPI file or URL**
5. Paste the URL:
   ```
   https://<your-ngrok-url>/openapi.json
   ```
   (or upload the downloaded `openapi.json` file directly)
6. Click **Next**
7. Orchestrate will detect the available operations. Select:
   - ✓ `POST /pipeline/run` — *Process all receipts for an expense report*
   - ✓ `GET /health` — *Liveness probe* (optional)
8. Click **Add skills**

---

## Step 3 — Configure the Skill

After importing:
1. Open the **pipeline/run** skill
2. Set the **input field mappings**:

| Orchestrate field | Maps to |
|---|---|
| Receipt files | `files[]` |
| Report ID | `report_id` |
| Employee ID | `employee_id` |

3. Set the **output field mappings**:

| Orchestrate output | Response field |
|---|---|
| Summary | `summary` |
| Matched count | `matched` |
| Results | `results` |

---

## Step 4 — Test the Skill in Orchestrate

In your Orchestrate assistant, type:
```
File these receipts from my Bengaluru trip.
```

Orchestrate will:
1. Ask for the receipt files
2. Ask for the report ID and employee ID (or infer from context)
3. Call `POST /pipeline/run`
4. Display the structured results

---

## Step 5 — Seed Layer 3 (for full end-to-end test)

Before running the full pipeline test, seed Layer 3 with matching
corporate card transactions. Run these curl commands against Layer 3:

```bash
# Replace http://localhost:8001 with your Layer 3 URL

# Seed transaction matching hotel_marriott.pdf
curl -X POST http://localhost:8001/expense/v4/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "txn_id": "TXN-001",
    "employee_id": "EMP001",
    "vendor": "Marriott",
    "amount": 10530.00,
    "currency": "INR",
    "transaction_date": "2026-07-21",
    "status": "UNMATCHED"
  }'

# Seed transaction matching taxi_ola.pdf
curl -X POST http://localhost:8001/expense/v4/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "txn_id": "TXN-002",
    "employee_id": "EMP001",
    "vendor": "Ola Cabs",
    "amount": 441.00,
    "currency": "INR",
    "transaction_date": "2026-07-21",
    "status": "UNMATCHED"
  }'

# Seed transaction matching flight_indigo.pdf
curl -X POST http://localhost:8001/expense/v4/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "txn_id": "TXN-003",
    "employee_id": "EMP001",
    "vendor": "IndiGo",
    "amount": 3880.00,
    "currency": "INR",
    "transaction_date": "2026-07-21",
    "status": "UNMATCHED"
  }'

# Seed transaction matching meals_restaurant.pdf
curl -X POST http://localhost:8001/expense/v4/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "txn_id": "TXN-004",
    "employee_id": "EMP001",
    "vendor": "Mainland China",
    "amount": 1851.00,
    "currency": "INR",
    "transaction_date": "2026-07-20",
    "status": "UNMATCHED"
  }'

# Seed transaction matching meals_conference.pdf
curl -X POST http://localhost:8001/expense/v4/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "txn_id": "TXN-005",
    "employee_id": "EMP001",
    "vendor": "NASSCOM",
    "amount": 10030.00,
    "currency": "INR",
    "transaction_date": "2026-07-20",
    "status": "UNMATCHED"
  }'
```

> **Note:** `misc_pharmacy.pdf` is a cash receipt — no card transaction to match.
> It will appear in results with `matched_txn_id: null` and `payment_type: OUT_OF_POCKET`.

---

## Confirming operationId Values

FastAPI auto-generates `operationId` values. The key endpoints in `/openapi.json` will be:

| Path | operationId |
|---|---|
| `POST /pipeline/run` | `run_pipeline_pipeline_run_post` |
| `GET /health` | `health_health_get` |
| `GET /watsonx/status` | `watsonx_status_watsonx_status_get` |

These are Orchestrate-compatible (no special characters).
