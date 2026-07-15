# SAP Concur Stub

An enterprise-grade FastAPI stub that faithfully simulates the SAP Concur v4 REST API for the **IBM watsonx AI Expense Claims Copilot** prototype.

The stub implements the full business validation pipeline — employee validation, trip matching, duplicate detection, travel policy enforcement, hotel itemization, corporate card matching, and audit logging — making the AI Middleware believe it is communicating with real SAP Concur.

---

## Architecture Position

```
watsonx Orchestrate  →  AI Middleware (OCR / Extraction)  →  SAP Concur Stub (this project)
   Layer 1–3                     Layer 4                              Layer 5
```

The stub receives **only structured JSON** from Layer 2 — never raw receipt images or base64 data.

---

## Quick Start

### Prerequisites
- Python 3.11+
- `pip`

### Install & Run

```bash
cd concur-stub
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The server starts at **http://localhost:8000**.

On first startup:
1. The SQLite database `concur_stub.db` is created.
2. All 13 tables are initialised.
3. Seed data is inserted: 2 travel policies, 4 employees, 5 trips, 19 card transactions.

### URLs

| URL | Description |
|---|---|
| http://localhost:8000/docs | Interactive OpenAPI spec (Swagger UI) |
| http://localhost:8000/redoc | Alternative API documentation |
| http://localhost:8000/admin | Admin dashboard |
| http://localhost:8000/health | Liveness probe |

---

## Seeded Demo Data

### Travel Policies

| Policy | Hotel Limit | Meal Limit | Max Flight Class | Currencies |
|---|---|---|---|---|
| `STANDARD` | ₹6,000/night | ₹1,000/meal | ECONOMY | INR |
| `EXECUTIVE` | ₹12,000/night | ₹2,500/meal | BUSINESS | INR, USD, GBP, EUR |

### Employees

| ID | Name | Policy | City |
|---|---|---|---|
| `EMP001` | Priya Sharma | STANDARD | Bengaluru |
| `EMP002` | Arjun Mehta | STANDARD | Mumbai |
| `EMP003` | Kavita Nair | EXECUTIVE | Delhi |
| `EMP004` | Rohan Desai | EXECUTIVE | Hyderabad |

---

## API Quick Reference

All Concur-facing endpoints use the `/api/v4/` prefix.

### Create Expense Report (shell)
```bash
curl -s -X POST http://localhost:8000/api/v4/expense-reports \
  -H "Content-Type: application/json" \
  -d '{
    "reportId":        "RPT001",
    "employeeId":      "EMP001",
    "reportName":      "Bengaluru Trip July 2026",
    "businessPurpose": "Client workshop",
    "travelPolicy":    "STANDARD",
    "expenseCategory": "TRAVEL"
  }' | python3 -m json.tool
```

### Submit Expenses (bulk — triggers the 9-step pipeline)
```bash
curl -s -X POST http://localhost:8000/api/v4/expense-reports/RPT001/expenses \
  -H "Content-Type: application/json" \
  -d '{
    "employeeId": "EMP001",
    "expenses": [
      {
        "expenseType":     "HOTEL",
        "vendor":          "Marriott",
        "amount":          18000.0,
        "currency":        "INR",
        "transactionDate": "2026-07-20",
        "city":            "Bengaluru",
        "paymentType":     "CORPORATE_CARD",
        "itemization": [
          { "nightDate": "2026-07-20", "roomRate": 5500.0, "taxes": 990.0, "incidentals": 150.0 },
          { "nightDate": "2026-07-21", "roomRate": 5500.0, "taxes": 990.0, "incidentals": 150.0 }
        ]
      },
      {
        "expenseType":     "TAXI",
        "vendor":          "Ola",
        "amount":          650.0,
        "currency":        "INR",
        "transactionDate": "2026-07-20",
        "city":            "Bengaluru",
        "paymentType":     "CORPORATE_CARD"
      }
    ]
  }' | python3 -m json.tool
```

### Get Employee Profile
```bash
curl http://localhost:8000/api/v4/employees/EMP001 | python3 -m json.tool
```

### Get Travel Policy Rules
```bash
curl http://localhost:8000/api/v4/travel-policies/STANDARD | python3 -m json.tool
```

### Submit Report for Approval
```bash
curl -s -X PATCH http://localhost:8000/api/v4/expense-reports/RPT001/submit | python3 -m json.tool
```

### Inject a Card Transaction (test harness)
```bash
curl -s -X POST http://localhost:8000/admin/card-transactions \
  -H "Content-Type: application/json" \
  -d '{
    "transactionId":   "CCT099",
    "employeeId":      "EMP001",
    "vendor":          "Custom Vendor",
    "amount":          1200.0,
    "currency":        "INR",
    "transactionDate": "2026-07-20",
    "cardLastFour":    "4242"
  }' | python3 -m json.tool
```

---

## Demo Scenarios

### Scenario 1 — Happy Path
- Employee: `EMP001` (STANDARD, Bengaluru)
- Seed trip: `TRIP001` (Bengaluru, Jul 20–23 2026)
- Seed card transactions: `CCT001` (Marriott ₹18,000), `CCT003` (Ola ₹650)
- **Expected result:** `DRAFT` status, all expenses `MATCHED`, zero warnings

### Scenario 2 — Policy Violation
- Employee: `EMP002` (STANDARD, Hyderabad)
- Submit hotel with room rate ₹7,500/night (STANDARD limit: ₹6,000)
- **Expected result:** `DRAFT` status, `HOTEL_NIGHTLY_LIMIT_EXCEEDED` warning per exceeded night

### Scenario 3 — Unmatched Trip
- Submit any expense for a city/date with no seeded trip record
- **Expected result:** `MANUAL_REVIEW` status, `TRIP_NOT_MATCHED` report-level warning

### Scenario 4 — Duplicate Detection
- Submit the same expense for the same employee twice
- **Expected result:** Second submission returns `DUPLICATE_RECEIPT_DETECTED` expense-level warning

---

## Running Unit Tests

```bash
cd concur-stub
pytest tests/ -v --ignore=tests/smoke_test.py
```

## Running Smoke Tests (requires live server)

```bash
# Terminal 1
uvicorn main:app --reload --port 8000

# Terminal 2
cd concur-stub
pytest tests/smoke_test.py -v -m smoke
```

---

## Validation Pipeline Summary

| Step | Classification | Behaviour on Failure |
|---|---|---|
| 1. Employee validation | PRE-FLIGHT | HTTP 404/403 — abort |
| 2. Report validation | PRE-FLIGHT | HTTP 404/409/403 — abort |
| 3. Full pre-flight (type, currency, mandatory fields) | PRE-FLIGHT | HTTP 422 — abort with all errors |
| 4. Audit: report opened | WRITE | Always proceeds |
| 5. Trip matching | WARNING | `MANUAL_REVIEW` + `TRIP_NOT_MATCHED` |
| 6. Duplicate detection | WARNING | `DUPLICATE_RECEIPT_DETECTED` |
| 7. Policy validation | WARNING | Policy-specific warning codes |
| 8. Card transaction matching | WARNING | `CARD_TRANSACTION_NOT_MATCHED` |
| 9. Persist & respond | WRITE | Saves all data, returns envelope |

---

## SAP Concur Replacement Seam

To point the AI Middleware at real SAP Concur instead of this stub:

1. Change the base URL in Orchestrate's skill registry from `http://localhost:8000` to `https://us.api.concursolutions.com`
2. Swap the `X-Api-Key` header for a Concur OAuth 2.0 JWT bearer token

No payload changes are required in Layer 2.

---

## Project Structure

```
concur-stub/
├── main.py                  # App factory + lifespan
├── config.py                # Settings (pydantic-settings)
├── database.py              # SQLAlchemy engine + session factory
├── seed.py                  # Reference data seed (idempotent)
├── models/                  # 13 SQLAlchemy ORM models
├── schemas/                 # 7 Pydantic v2 schema files
├── repositories/            # 7 database access modules
├── services/
│   ├── expense_service.py   # 9-step validation pipeline
│   ├── policy_engine.py     # Composable policy validators
│   ├── trip_matching_service.py
│   ├── duplicate_detection.py
│   └── audit_service.py
├── routers/                 # 8 FastAPI router files
├── templates/               # 6 Jinja2 HTML templates
├── static/style.css         # IBM Carbon-inspired CSS
└── tests/                   # Unit + integration + smoke tests
```
