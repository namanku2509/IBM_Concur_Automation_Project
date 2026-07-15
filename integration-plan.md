# Bulk Receipt Automation Pipeline — Industry-Grade Integration Plan

## Overview

This plan integrates three independently-built layers into a production-quality automation
pipeline. Beyond simply wiring the layers together, it elevates every component to
industry standard: proper API contract alignment, correlation tracing, structured error
propagation, type normalisation, a parallel receipt processing engine, robust frontend
data binding, and a production-ready developer experience with env files and startup docs.

**Port assignments (fixed):**
- Layer 3 (concur-stub): **8001**
- Layer 2 (layer2-middleware): **8000**
- BFF (expense-copilot/bff): **4000**
- Frontend (expense-copilot/frontend): **3000**

---

## Architecture — End-to-End Data Flow

```
BROWSER :3000 (React + IBM Carbon)
    │ POST /api/report           → create report shell
    │ GET  /api/report/:id/transactions  → load card transactions
    │ POST /api/report/:id/receipts      → upload + process PDFs
    │ POST /api/report/:id/submit        → final submit
    ▼
BFF :4000 (Express + Node.js)
    │ Validates, sessions, orchestrates
    │ POST /api/v4/expense-reports                  → register shell   [Layer 3]
    │ GET  /api/v4/card-transactions?employeeId=... → list card txns   [Layer 3]
    │ POST /pipeline/run                            → OCR + AI + match [Layer 2]
    │ PATCH /api/v4/expense-reports/:id/submit      → finalise report  [Layer 3]
    ▼
LAYER 2 :8000 (FastAPI + Docling + Ollama)
    │ Stage 1: OCR     — Docling (local, no API key)
    │ Stage 2: Categorise — Ollama llama3.2:3b (local)
    │ Stage 3: Extract — Ollama + type-specific prompts
    │ Stage 4: Match   — rapidfuzz vs Layer 3 card transactions
    │ Stage 5: Submit  — POST /api/v4/expense-reports/:id/expenses [Layer 3]
    │          Register — POST /api/v4/receipts/register           [Layer 3]
    ▼
LAYER 3 :8001 (FastAPI + SQLite)
    9-step validation: employee → report → preflight →
      audit → trip-match → dedup → policy → card-match → persist
```

---

## Sub-Task 1 — Fix BFF Base URLs and Layer 2 Endpoint Path

**Status:** [ ] pending

### Intent
The BFF cannot reach any real service. Both base URLs are hardcoded to a defunct mock
on port 5000, and the Layer 2 call path is wrong. This is the highest-priority blocker.

### Expected Outcomes
- `bff/config.js` defaults resolve to real services with env-var override capability.
- `bff/services/layer2Service.js` calls `POST /pipeline/run` (the real Layer 2 entry point).
- Session secret is env-var driven (not a hardcoded string).

### Todo List
1. **`expense-copilot/bff/config.js`** — change default `LAYER2_BASE_URL` from
   `http://localhost:5000/l2` → `http://localhost:8000`, and `LAYER3_BASE_URL` from
   `http://localhost:5000/l3` → `http://localhost:8001`.
2. **`expense-copilot/bff/services/layer2Service.js` line 23** — change call path from
   `/receipts/process` → `/pipeline/run`. Also add a `timeout: 120000` option to
   `axios.post` (Docling + Ollama can take 30–90s per batch).
3. **`expense-copilot/bff/server.js`** — replace hardcoded session secret
   `'expense-copilot-secret'` with `process.env.SESSION_SECRET || 'expense-copilot-dev-secret'`.

### Relevant Context
- [`expense-copilot/bff/config.js`](expense-copilot/bff/config.js:4) lines 4–5.
- [`expense-copilot/bff/services/layer2Service.js`](expense-copilot/bff/services/layer2Service.js:23) line 23.
- [`expense-copilot/bff/server.js`](expense-copilot/bff/server.js:13) line 13.
- Layer 2 real endpoint: `POST /pipeline/run` declared in
  [`layer2-middleware/src/routes/pipeline.py`](layer2-middleware/src/routes/pipeline.py:35).

---

## Sub-Task 2 — Fix BFF → Layer 3 API Path Contracts

**Status:** [ ] pending

### Intent
All four functions in `bff/services/layer3Service.js` call Layer 3 at paths that do not
exist. Every path is missing the `/api/v4/` prefix, two use wrong HTTP methods, one calls
a non-existent endpoint, and the request body field names are all snake_case where Layer 3
expects camelCase aliases.

### Expected Outcomes
- `getEmployee()` calls `GET /api/v4/employees/{id}`.
- `createReport()` calls `POST /api/v4/expense-reports` with a camelCase body.
- `getTransactions()` calls `GET /api/v4/card-transactions?employeeId=EMP001`.
- `submitReport()` calls `PATCH /api/v4/expense-reports/{id}/submit` (no body needed — it
  is a status-transition-only endpoint that returns `{ reportId, status, message }`).

### Todo List
1. **`bff/services/layer3Service.js` — `getEmployee()`** — update URL to
   `${LAYER3_BASE_URL}/api/v4/employees/${employeeId}`.
2. **`createReport()`** — update URL to `${LAYER3_BASE_URL}/api/v4/expense-reports`.
   Rewrite body to use camelCase aliases that match `ExpenseReportCreate`:
   `{ reportId, employeeId, reportName, businessPurpose, travelPolicy: policy,
   expenseCategory: reportCategory, currency: 'INR' }`.
3. **`getTransactions()`** — update URL to `${LAYER3_BASE_URL}/api/v4/card-transactions`.
   Replace `params.policy` with `params.employeeId` (Layer 3 filters by `employeeId`
   query param — camelCase alias, verified in
   [`concur-stub/routers/card_transactions.py`](concur-stub/routers/card_transactions.py:38)).
4. **`submitReport()`** — change `axios.post` → `axios.patch`.
   Update URL to `${LAYER3_BASE_URL}/api/v4/expense-reports/${reportId}/submit`.
   No request body needed. Response shape is `{ reportId, status, message }`.
5. In the same file, add a shared `LAYER3_HEADERS` constant:
   `{ 'X-Api-Key': process.env.LAYER3_API_KEY || 'concur-stub-dev-key' }` and pass it
   in every request.

### Relevant Context
- [`expense-copilot/bff/services/layer3Service.js`](expense-copilot/bff/services/layer3Service.js) — all four functions.
- Layer 3 routes confirmed in:
  - [`concur-stub/routers/employees.py`](concur-stub/routers/employees.py:23) — `GET /employees/{id}`
  - [`concur-stub/routers/expense_reports.py`](concur-stub/routers/expense_reports.py:37) — `POST /expense-reports`
  - [`concur-stub/routers/card_transactions.py`](concur-stub/routers/card_transactions.py:29) — `GET /card-transactions?employeeId=`
  - [`concur-stub/routers/expense_reports.py`](concur-stub/routers/expense_reports.py:223) — `PATCH /expense-reports/{id}/submit`
- Layer 3 `ExpenseReportCreate` schema uses camelCase aliases:
  [`concur-stub/schemas/expense_report.py`](concur-stub/schemas/expense_report.py:27).
- Layer 3 API key: `concur-stub-dev-key` from
  [`concur-stub/config.py`](concur-stub/config.py:32).

---

## Sub-Task 3 — Fix BFF Receipt Response Mapping and Submit Payload Builder

**Status:** [ ] pending

### Intent
After Layer 2 returns a `PipelineResult`, the BFF reads `data.expenses` and
`data.processingWarnings` — fields that don't exist in the actual response shape. The real
shape has `data.results` (array of `ReceiptResult`). Additionally, the frontend's
`ReportFolderPage.js` renders `expense.matchedTxnId` from each processed expense, but
Layer 2 returns `matched_txn_id` (snake_case). Both mismatches are fixed here along with
the submit payload builder that must translate `ReceiptResult` objects into the
`ExpensesSubmitRequest` envelope that Layer 3 expects.

### Expected Outcomes
- BFF receipt handler reads `data.results` from Layer 2's `PipelineResult`.
- Session stores the results list correctly.
- BFF returns `expenses: data.results` and `summary: data.summary` to the frontend.
- Frontend receives `matchedTxnId` (camelCase) correctly — the BFF normalises field names.
- On `POST /api/report/:id/submit`, the BFF builds a valid `ExpensesSubmitRequest` body
  from the stored `results` and POSTs expenses to Layer 3 BEFORE calling the PATCH submit
  transition — in the correct 2-step sequence.
- The submit response returns `{ reportId, status, message }` to the frontend (no `confirmationId` — the frontend must be updated to show `status` instead).

### Todo List
1. **`bff/routes/report.js` receipt handler (lines 141–154):**
   - Change `processedExpenses: data.expenses` → normalise `data.results` to camelCase
     before storing and returning (the frontend's `ProcessedExpensesTable.js` expects
     camelCase field names). Map each `ReceiptResult` result:
     `{ expenseType: r.expense_type, vendor: r.vendor, amount: r.amount,
        currency: r.currency, transactionDate: r.transaction_date, city: r.city,
        paymentType: r.payment_type, matchedTxnId: r.matched_txn_id,
        matchConfidence: r.match_confidence, expenseId: r.expense_id,
        filename: r.filename, status: r.status, warnings: r.warnings || [] }`
   - Change `warnings: data.processingWarnings` → `data.results.flatMap(r => r.warnings || [])`
   - Return `expenses: <normalised array>` and `summary: data.summary` to the frontend.
2. **`bff/routes/report.js` submit handler (lines 170–211):** Replace the single
   `layer3.submitReport()` call with a 2-step sequence:
   - Step A: Build `expensesPayload` from `folder.processedExpenses` (each `ReceiptResult`)
     mapped to `ExpenseInput` shape. Use a helper function `buildExpenseInput(result)` that
     translates snake_case pipeline fields to camelCase Layer 3 fields.
   - Step B: Call a new `layer3.postExpenses(reportId, expensesPayload)` function to
     `POST /api/v4/expense-reports/{id}/expenses`.
   - Step C: Call `layer3.submitReport(reportId)` for the `PATCH /submit` transition.
   - Collect warnings from the `postExpenses` response and include in the final reply.
3. **`bff/services/layer3Service.js`** — add a `postExpenses(reportId, payload)` function
   that calls `POST /api/v4/expense-reports/${reportId}/expenses` with the
   `ExpensesSubmitRequest` body.
4. **`expense-copilot/frontend/src/pages/ReportFolderPage.js` line 105** — change
   `setProcessedExpenses(data.expenses)` → `setProcessedExpenses(data.expenses || [])`.
5. **`expense-copilot/frontend/src/pages/ReportFolderPage.js` line 106** — change
   `setWarnings(data.warnings || [])` — keep as-is (BFF now collects them correctly).
6. **`expense-copilot/frontend/src/pages/ReportFolderPage.js` line 219** — change
   `e.matchedTxnId` → `e.matched_txn_id` to match Layer 2's snake_case `ReceiptResult`
   field. Also update `ProcessedExpensesTable.js` if it references `matchedTxnId`.
7. **`expense-copilot/frontend/src/pages/ReportFolderPage.js` line 136** — `data.confirmationId`
   does not exist in Layer 3's `StatusResponse`. Change to show `data.status` and `data.message`
   in the confirmation display.

### Relevant Context
- Layer 2 `PipelineResult` shape: `{ results: ReceiptResult[], summary }` —
  [`layer2-middleware/src/models/pipeline_models.py`](layer2-middleware/src/models/pipeline_models.py:139).
- `ReceiptResult` fields (snake_case): `matched_txn_id`, `expense_type`, `vendor`, `amount`,
  `currency`, `transaction_date`, `city`, `payment_type`, `hotel_detail`, `taxi_detail`,
  `airfare_detail`, `meal_detail` —
  [`layer2-middleware/src/models/pipeline_models.py`](layer2-middleware/src/models/pipeline_models.py:57).
- Layer 3 `ExpensesSubmitRequest` body: `{ employeeId, expenses: [ExpenseInput] }` —
  [`concur-stub/schemas/expense.py`](concur-stub/schemas/expense.py:229).
- Layer 3 `PATCH /submit` returns `{ reportId, status, message }` —
  [`concur-stub/schemas/common.py`](concur-stub/schemas/common.py:295).
- [`expense-copilot/frontend/src/pages/ReportFolderPage.js`](expense-copilot/frontend/src/pages/ReportFolderPage.js:105).
- [`expense-copilot/frontend/src/components/ProcessedExpensesTable.js`](expense-copilot/frontend/src/components/ProcessedExpensesTable.js).

---

## Sub-Task 4 — Fix Layer 2 → Layer 3 Endpoint Paths + Auth Header

**Status:** [ ] pending

### Intent
Layer 2's `src/config.py` `LAYER3_ENDPOINTS` dict maps to paths that don't exist on
Layer 3. Three paths are wrong, one calls a non-existent endpoint (`link_transaction`),
and one has the wrong attach-receipt design (Layer 3 stores metadata only, not binary).
All `httpx` calls also lack the `X-Api-Key` header that Layer 3 documents as required.

### Expected Outcomes
- `submit_expense` path resolves to `/api/v4/expense-reports/{report_id}/expenses`.
- `available_transactions` path resolves to `/api/v4/card-transactions`.
- `attach_receipt` is replaced by `register_receipt` → `/api/v4/receipts/register`.
- `link_transaction` is removed (Layer 3 handles card matching in its own Step 8).
- Every httpx request carries `X-Api-Key: concur-stub-dev-key`.

### Todo List
1. **`layer2-middleware/src/config.py` — `LAYER3_ENDPOINTS`** — rewrite to:
   ```python
   LAYER3_ENDPOINTS = {
       "submit_expense":        "/api/v4/expense-reports/{report_id}/expenses",
       "available_transactions": "/api/v4/card-transactions",
       "register_receipt":       "/api/v4/receipts/register",
   }
   ```
2. **`src/config.py`** — add `LAYER3_API_KEY: str = os.getenv("LAYER3_API_KEY", "concur-stub-dev-key")`.
3. **`layer2-middleware/src/services/concur_client.py`** — add a shared headers constant
   at module level: `_L3_HEADERS = lambda: {"X-Api-Key": config.LAYER3_API_KEY}`.
   Add `headers=_L3_HEADERS()` to every `httpx.AsyncClient` request.
4. **`concur_client.py` — `fetch_available_transactions()`** — update the `params` dict
   from `{"employee_id": employee_id, "report_id": report_id}` to
   `{"employeeId": employee_id}` (Layer 3 uses camelCase query alias, ignores report_id).
5. **`concur_client.py` — `fetch_available_transactions()` response mapping** — Layer 3
   returns `CardTransactionListResponse` with `{ employeeId, transactions: [...], total }`.
   Each transaction has `transactionId` (not `txn_id`), `transactionDate` (not
   `transaction_date`). Update `AvailableTransaction` or add a mapping step to bridge
   the camelCase Layer 3 response to the snake_case `AvailableTransaction` model.
6. **`concur_client.py` — `attach_receipt()`** — replace the binary multipart upload with
   a JSON POST to `/api/v4/receipts/register` with body
   `{ employeeId, fileName, mimeType, receiptHash, ocrConfidence }`.
   Update signature to `register_receipt(employee_id, receipt_payload, filename)`.
7. **`concur_client.py` — `link_transaction()`** — convert to a no-op stub (keep the
   function signature to avoid breaking callers, but log a debug message and return
   immediately without making any HTTP call, since Layer 3 owns card matching).
8. **`layer2-middleware/src/routes/pipeline.py` Stage 5** — replace `attach_receipt` call
   with `register_receipt` call; remove `link_transaction` call entirely.
   Also update the import list at line 94 to match the renamed functions.

### Relevant Context
- [`layer2-middleware/src/config.py`](layer2-middleware/src/config.py:46) — `LAYER3_ENDPOINTS`.
- [`layer2-middleware/src/services/concur_client.py`](layer2-middleware/src/services/concur_client.py) — all functions.
- [`concur-stub/routers/card_transactions.py`](concur-stub/routers/card_transactions.py:38) — `employeeId` query alias.
- [`concur-stub/routers/receipts.py`](concur-stub/routers/receipts.py:27) — `POST /receipts/register` with `ReceiptRegisterRequest`.
- [`concur-stub/schemas/card_transaction.py`](concur-stub/schemas/card_transaction.py:20) — `CardTransactionResponse` camelCase fields.
- Layer 2 `AvailableTransaction`: [`layer2-middleware/src/models/concur_models.py`](layer2-middleware/src/models/concur_models.py:88).

---

## Sub-Task 5 — Fix Layer 2 → Layer 3 Submit Payload Contract and Type Normalisation

**Status:** [ ] pending

### Intent
Layer 2's `schema_mapper.py` builds a single flat `ExpensePayload` per receipt and posts
it directly to Layer 3. But Layer 3's POST expenses endpoint expects an
`ExpensesSubmitRequest` envelope: `{ employeeId, expenses: [ExpenseInput] }`. Beyond the
wrapping issue, there are four field-level contract mismatches that must all be fixed:

1. **`MEALS` vs `MEAL`** — Layer 2 uses `"MEALS"` throughout; Layer 3's `ExpenseType`
   enum only accepts `"MEAL"`. Every meal expense submitted would be rejected with 422.
2. **Hotel detail mapping** — Layer 2 sends a `hotel_detail` flat object; Layer 3 requires
   an `itemization` array of nightly lines (`HotelItemizationInput`).
3. **`ExpensePayload` vs `ExpenseInput`** — Layer 2's internal payload model has different
   field names/structure than Layer 3's `ExpenseInput` Pydantic schema.
4. **`SubmitResponse` shape** — Layer 2 expects `{ expense_id, report_id, status, warnings }`
   but Layer 3 returns `ExpensesSubmitResponse` with `{ reportId, status, processedExpenses: [...]}`
   so `expense_id` must be extracted from `processedExpenses[0].expenseId`.

### Expected Outcomes
- All `"MEALS"` values are normalised to `"MEAL"` before reaching Layer 3.
- Hotel `hotel_detail` is translated into `itemization` nightly lines in `schema_mapper.py`.
- `concur_client.submit_expense()` wraps the payload in the `ExpensesSubmitRequest` envelope.
- `SubmitResponse` correctly extracts `expense_id` from `processedExpenses[0].expenseId`.
- `REGISTRATION` expense type is handled gracefully (mapped to `MEAL` or logged and skipped,
  since Layer 3 has no `REGISTRATION` type — its `ExpenseType` enum is: HOTEL, MEAL, TAXI, FLIGHT).

### Todo List
1. **`layer2-middleware/src/services/schema_mapper.py`** — add a type normalisation step
   at the top of `build_expense_payload()`:
   ```python
   type_map = {"MEALS": "MEAL", "REGISTRATION": "MEAL"}
   normalised_type = type_map.get(extracted.expense_type, extracted.expense_type)
   ```
2. **`schema_mapper.py` — hotel detail translation** — when `normalised_type == "HOTEL"`
   and `extracted.hotel_detail` exists, build an `itemization` list instead of
   `hotel_detail`. If `num_nights >= 1`, generate one `HotelItemizationInput`-compatible
   dict per night: `{ nightDate: date, roomRate: nightly_rate, taxes: tax/nights,
   incidentals: 0.0 }`. If no itemization can be derived (missing hotel data), add a
   single-line fallback with the full amount as `roomRate`.
3. **`schema_mapper.py`** — rename `ExpensePayload` usage to build the final dict
   compatible with `ExpenseInput` camelCase aliases:
   `expenseType`, `transactionDate`, `paymentType`, `airfareDetail`, `taxiDetail`,
   `mealDetail`, `itemization`, `ocrConfidence`.
4. **`layer2-middleware/src/models/concur_models.py` — `SubmitResponse`** — update to
   match Layer 3's actual `ExpensesSubmitResponse`:
   Add `processed_expenses: list` field. Update `expense_id` to extract from
   `processed_expenses[0]["expenseId"]` if present.
5. **`layer2-middleware/src/services/concur_client.py` — `submit_expense()`** — wrap the
   payload in `{ "employeeId": employee_id, "expenses": [payload_dict] }` before posting.
   Update the function signature to accept `employee_id: str` as a parameter.
6. **`layer2-middleware/src/routes/pipeline.py`** — pass `employee_id` to
   `submit_expense(report_id, employee_id, expense_payload)`.
7. **`layer2-middleware/src/services/categorisation_service.py` line 29`** — note that
   `_VALID_TYPES` already includes `"REGISTRATION"`. The normalisation in schema_mapper
   handles the type mapping; no change needed here.

### Relevant Context
- [`layer2-middleware/src/services/schema_mapper.py`](layer2-middleware/src/services/schema_mapper.py:26) — `build_expense_payload()`.
- [`layer2-middleware/src/models/concur_models.py`](layer2-middleware/src/models/concur_models.py:51) — `ExpensePayload` and `SubmitResponse`.
- [`layer2-middleware/src/services/concur_client.py`](layer2-middleware/src/services/concur_client.py:42) — `submit_expense()`.
- Layer 3 `ExpenseInput` schema: [`concur-stub/schemas/expense.py`](concur-stub/schemas/expense.py:136) — uses camelCase aliases.
- Layer 3 `ExpenseType` enum: [`concur-stub/schemas/common.py`](concur-stub/schemas/common.py:54) — `HOTEL, MEAL, TAXI, FLIGHT` only.
- Hotel itemization required: [`concur-stub/services/expense_service.py`](concur-stub/services/expense_service.py:222) — Step 3 pre-flight.
- Layer 3 `ExpensesSubmitResponse`: [`concur-stub/schemas/common.py`](concur-stub/schemas/common.py:264).

---

## Sub-Task 6 — Fix Frontend Policy/Category Values + Response Field Bindings

**Status:** [ ] pending

### Intent
The frontend's `CreateReportPage.js` presents policy values like
`'TRAVEL_AND_EXPENSE_AP_NON_VAT'` which Layer 3 does not know about (it seeds `STANDARD`
and `EXECUTIVE`). These must match the actual seeded policy names. Several response field
bindings in `ReportFolderPage.js` reference wrong field names, and the transactions table
needs to display the correct fields from Layer 3's `CardTransactionResponse`.

### Expected Outcomes
- Policy dropdown shows `STANDARD` and `EXECUTIVE` matching Layer 3's seeded policies.
- Report categories passed to BFF match Layer 3's `expenseCategory` accepted values.
- Transactions table shows `transactionId`, `vendor`, `amount`, `transactionDate`,
  `status` from Layer 3's `CardTransactionResponse`.
- Processed expenses table renders correctly from Layer 2's `ReceiptResult` snake_case fields.
- Confirmation screen shows `status` and `message` (not a `confirmationId` that doesn't exist).

### Todo List
1. **`expense-copilot/frontend/src/pages/CreateReportPage.js`** — replace the `POLICIES`
   array with `STANDARD` and `EXECUTIVE` entries to match Layer 3's seeded `travel_policy_name`
   values (the `travelPolicy` field in `ExpenseReportCreate` must equal a seeded policy name).
2. **`expense-copilot/frontend/src/pages/ReportFolderPage.js` lines 105–106**:
   - `setProcessedExpenses(data.expenses || [])` — no change needed if Sub-Task 3 fixes BFF.
   - `setTransactions(data.transactions)` — keep; BFF returns `transactions` from Layer 3's
     `CardTransactionListResponse.transactions`.
3. **`expense-copilot/frontend/src/components/AvailableExpensesTable.js`** — fix the
   row mapper at line 57: change `id: t.txnId` → `id: t.transactionId`, and remove
   the `category: t.category` field (Layer 3's `CardTransactionResponse` has no `category`
   field — remove the column from `HEADERS` too and replace with `cardLastFour` or omit).
   Also fix `t.transactionDate` (already correct in the date cell).
4. **`expense-copilot/frontend/src/components/ProcessedExpensesTable.js`** — no changes
   needed. Once Sub-Task 3 makes the BFF normalise `data.results` to camelCase, this
   component already expects `e.expenseType`, `e.vendor`, `e.amount`,
   `e.transactionDate`, and `e.matchedTxnId` — all of which will now be correct.
5. **`expense-copilot/frontend/src/pages/ReportFolderPage.js` lines 133–142`** —
   replace `data.confirmationId` with `data.status` + `data.message` in the confirmation
   state, and update the confirmation tile to display both.
6. **`expense-copilot/frontend/src/pages/ReportFolderPage.js` line 84`** — `data.totalCount`
   from BFF. BFF returns `totalCount: data.transactions.total` from Layer 3's response
   (`CardTransactionListResponse.total`). Ensure BFF maps this correctly in Sub-Task 3.

### Relevant Context
- Layer 3 seeded policies: `STANDARD`, `EXECUTIVE` in
  [`concur-stub/seed.py`](concur-stub/seed.py:44).
- Layer 3 `CardTransactionResponse` fields (camelCase):
  [`concur-stub/schemas/card_transaction.py`](concur-stub/schemas/card_transaction.py:20).
- [`expense-copilot/frontend/src/components/AvailableExpensesTable.js`](expense-copilot/frontend/src/components/AvailableExpensesTable.js).
- [`expense-copilot/frontend/src/components/ProcessedExpensesTable.js`](expense-copilot/frontend/src/components/ProcessedExpensesTable.js).

---

## Sub-Task 7 — Layer 3: Add CORS, Fix `ExpenseType` Enum to Accept `MEAL` Properly, and Harden the `card-transactions` BFF Response

**Status:** [ ] pending

### Intent
Layer 3 does not have CORS middleware — any browser-facing call or cross-origin BFF call
will be blocked. Additionally the BFF's `getTransactions()` response needs to correctly
forward Layer 3's `CardTransactionListResponse` shape to the frontend (including
`totalCount` and normalised `transactions` array). This sub-task also ensures that Layer 3's
`card_transactions` router response is fully compatible with what the BFF needs to forward.

### Expected Outcomes
- Layer 3 has CORS configured to allow requests from `http://localhost:4000` (BFF)
  and `http://localhost:3000` (frontend).
- BFF `getTransactions()` correctly maps Layer 3's response and returns
  `{ reportId, totalCount, transactions }` to the frontend.
- `totalCount` in the BFF response equals `data.total` from Layer 3 (not `data.length`).

### Todo List
1. **`concur-stub/main.py`** — add `CORSMiddleware` after `FastAPI()` app creation:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:4000", "http://localhost:3000"],
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```
2. **`expense-copilot/bff/routes/report.js` — `GET /transactions` handler (lines 87–113)**:
   - Change `data.transactions` → `data.transactions` (correct already).
   - Change `data.totalCount` → `data.total` (Layer 3 returns `total`, not `totalCount`).
   - Return `{ reportId, totalCount: data.total, transactions: data.transactions }`.
3. **`expense-copilot/bff/services/layer3Service.js` — `getTransactions()`** — verify
   the function passes `employeeId` param correctly (from Sub-Task 2). No further change
   needed here if Sub-Task 2 is done.

### Relevant Context
- [`concur-stub/main.py`](concur-stub/main.py:76) — FastAPI app instance.
- [`concur-stub/schemas/card_transaction.py`](concur-stub/schemas/card_transaction.py:63) — `CardTransactionListResponse.total`.
- [`expense-copilot/bff/routes/report.js`](expense-copilot/bff/routes/report.js:87) — transaction handler.

---

## Sub-Task 8 — Add `.env` Files, `STARTUP.md`, and Request Timeout/Retry Config

**Status:** [ ] pending

### Intent
No `.env.example` file exists for either the BFF or Layer 3. Without startup docs, the
system cannot be run by anyone other than the original developer. Additionally, Docling +
Ollama processing can take 30–90 seconds per receipt — both the BFF and Layer 2's httpx
client need appropriate timeouts to avoid premature failures on large batches.

### Expected Outcomes
- Each service has a `.env.example` documenting all config variables with working defaults.
- A root `STARTUP.md` provides exact ordered startup commands for all five processes.
- BFF axios requests to Layer 2 use a 180s timeout.
- Layer 2's httpx client uses a 60s connect timeout and 120s read timeout for Layer 3 calls.
- Layer 2's `DRY_RUN` default in `.env.example` is changed from `true` → `false` (the
  integration should submit to Layer 3 by default).

### Todo List
1. Create **`concur-stub/.env.example`**:
   ```
   DB_PATH=concur_stub.db
   API_KEY=concur-stub-dev-key
   APP_TITLE=SAP Concur Stub
   APP_VERSION=1.0.0
   RECEIPTS_STORE_DIR=receipts_store
   CARD_MATCH_DATE_TOLERANCE_DAYS=2
   TRIP_DATE_TOLERANCE_DAYS=1
   ```
2. Update **`layer2-middleware/.env.example`**:
   - Change `DRY_RUN=true` → `DRY_RUN=false`.
   - Add `LAYER3_API_KEY=concur-stub-dev-key`.
3. Create **`expense-copilot/bff/.env.example`**:
   ```
   PORT=4000
   LAYER2_BASE_URL=http://localhost:8000
   LAYER3_BASE_URL=http://localhost:8001
   LAYER3_API_KEY=concur-stub-dev-key
   SESSION_SECRET=change-me-in-production
   ```
4. **`expense-copilot/bff/services/layer2Service.js`** — set axios timeout to 180000ms
   (3 minutes) on the `/pipeline/run` request.
5. **`layer2-middleware/src/services/concur_client.py`** — update all
   `httpx.AsyncClient(timeout=30.0)` instances to use a structured timeout:
   `httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=5.0))`.
6. Create root **`STARTUP.md`** with exact ordered startup steps:
   ```
   # Startup Order

   ## Prerequisites
   - Python 3.11+, Node.js 18+
   - Ollama installed and llama3.2:3b pulled: `ollama pull llama3.2:3b`

   ## Step 1 — Start Ollama (leave running)
   ollama serve

   ## Step 2 — Start Layer 3 (SAP Concur Stub) on port 8001
   cd concur-stub
   pip install -r requirements.txt
   cp .env.example .env
   uvicorn main:app --port 8001 --reload

   ## Step 3 — Start Layer 2 (AI Middleware) on port 8000
   cd layer2-middleware
   pip install -r requirements.txt
   cp .env.example .env   # set DRY_RUN=false
   uvicorn main:app --port 8000 --reload

   ## Step 4 — Start BFF on port 4000
   cd expense-copilot/bff
   npm install
   cp .env.example .env
   npm start

   ## Step 5 — Start Frontend on port 3000
   cd expense-copilot/frontend
   npm install
   npm start

   ## Health Checks
   Layer 3: http://localhost:8001/health
   Layer 2: http://localhost:8000/health
   BFF:     http://localhost:4000/health
   Frontend: http://localhost:3000
   ```

### Relevant Context
- [`layer2-middleware/.env.example`](layer2-middleware/.env.example:14) — `DRY_RUN=true`.
- [`layer2-middleware/src/services/concur_client.py`](layer2-middleware/src/services/concur_client.py:66) — all `timeout=30.0` occurrences.
- [`expense-copilot/bff/services/layer2Service.js`](expense-copilot/bff/services/layer2Service.js:22) — axios post with no timeout.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Layer 3 runs on **port 8001** | Avoids collision with Layer 2 on 8000 |
| Layer 3 owns card matching (Step 8) | Layer 2 does fuzzy pre-matching for confidence scoring; Layer 3 re-validates via its own exact matcher and persists the link atomically |
| `link_transaction` endpoint removed from Layer 2 | No such endpoint exists on Layer 3; duplicate matching is handled in Layer 3's Step 8 atomically |
| Binary receipt PDF not forwarded to Layer 3 | Layer 3's receipt store is metadata-only; Layer 2 retains OCR text and registers only hash + confidence |
| BFF does a **2-step submit** (post expenses → PATCH submit) | Layer 3 requires expenses to be added first (POST), then status transitioned (PATCH) — these are separate operations |
| `MEALS` normalised to `MEAL` in Layer 2 | Layer 3's `ExpenseType` enum is the system of record; Layer 2's internal type is normalised at the schema-mapper boundary |
| Hotel `hotel_detail` → `itemization` array | Layer 3 requires per-night lines for hotel expenses (Step 3 pre-flight); schema_mapper generates them from num_nights + nightly_rate |
| `REGISTRATION` mapped to `MEAL` | Layer 3 has no `REGISTRATION` type; registration fees are treated as meal/entertainment expenses |
| BFF forwards `X-Api-Key` to Layer 3 | Layer 3 documents the header as required for all calls |
| Axios timeout 180s (BFF → Layer 2) | Docling + Ollama processing a batch of 5–6 receipts can take 60–120s on Apple Silicon |
| httpx structured timeout (Layer 2 → Layer 3) | Layer 3 SQLite commits can pause briefly; structured timeout avoids false failures |
| CORS on Layer 3 for BFF and frontend origins | BFF makes direct XHR calls to Layer 3 during `/health`; frontend may call BFF which then hits Layer 3 |

---

## Integration Test — Happy Path Walkthrough

After all sub-tasks complete, this sequence should succeed end-to-end:

```
1. Open http://localhost:3000
2. Fill form: "Bengaluru Trip July 2026" | "Client workshop" | STANDARD | CUSTOMER_CLIENT_RELATED_TRAVEL
3. Click "Create Expense Report"
   → BFF: POST /api/v4/expense-reports with employeeId=EMP001
   → Layer 3: returns { reportId: "RPT-XXXX", status: "DRAFT" }
   → BFF: stores in session, returns reportId
   → Frontend: navigates to /report/RPT-XXXX

4. Transactions table auto-loads
   → BFF: GET /api/v4/card-transactions?employeeId=EMP001
   → Layer 3: returns 6 transactions (CCT001–CCT006)
   → Table shows: Marriott ₹18000, IndiGo ₹5500, Ola ₹650, etc.

5. Upload hotel_receipt.pdf + taxi_receipt.pdf
   → BFF: POST /pipeline/run to Layer 2 (180s timeout)
   → Layer 2 Stage 1: Docling OCR → raw text
   → Layer 2 Stage 2: Ollama → "HOTEL" + "TAXI"
   → Layer 2 Stage 3: Ollama → structured fields
   → Layer 2 Stage 4: GET /api/v4/card-transactions?employeeId=EMP001
                       rapidfuzz: Marriott score 0.92 ✓ | Ola score 0.95 ✓
   → Layer 2 Stage 5: POST /api/v4/expense-reports/RPT-XXXX/expenses (2 expenses)
                       POST /api/v4/receipts/register (metadata only)
   → Layer 3: 9-step pipeline → MATCHED, MATCHED, no warnings
   → BFF: stores results, returns to frontend

6. Processed Expenses table shows 2/2 matched
7. Click "Submit Report"
   → BFF Step A: POST /api/v4/expense-reports/RPT-XXXX/expenses (final validation)
   → BFF Step B: PATCH /api/v4/expense-reports/RPT-XXXX/submit
   → Layer 3: transitions DRAFT → SUBMITTED
   → Frontend: shows "Report Submitted Successfully ✅ Status: SUBMITTED"
```
