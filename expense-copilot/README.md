# Expense Claims Copilot — Layer 1

AI-powered Expense Claims Copilot frontend and orchestration layer.
Built with React, IBM Carbon Design System, and Node.js/Express.

---

## Project Structure

```
expense-copilot/
├── frontend/    React app (employee-facing UI)          → runs on port 3000
├── bff/         Backend for Frontend (Node + Express)   → runs on port 4000
├── mocks/       Mock Layer 2 and Layer 3 API servers    → runs on port 5000
└── README.md
```

---

## How to Run (Development)

You need **three terminals** running simultaneously.

### Terminal 1 — Mock Servers (Layer 2 + Layer 3)

```bash
cd mocks
npm start
```

Runs on `http://localhost:5000`
- Layer 3 (Concur Stub mock): `http://localhost:5000/l3`
- Layer 2 (AI Middleware mock): `http://localhost:5000/l2`

---

### Terminal 2 — BFF Server

```bash
cd bff
npm start
```

Runs on `http://localhost:4000`

---

### Terminal 3 — Frontend

```bash
cd frontend
npm start
```

Runs on `http://localhost:3000`

---

## Swapping Mock for Real Layer 2 / Layer 3

The BFF reads Layer 2 and Layer 3 URLs from environment variables.
Create a `bff/.env` file to override:

```
LAYER2_BASE_URL=https://real-layer2-api.example.com
LAYER3_BASE_URL=https://real-layer3-api.example.com
```

No code changes required.

---

## Implementation Status

| Sub-Task | Description | Status |
|---|---|---|
| 1 | Project Scaffolding | ✅ Done |
| 2 | Mock Servers | ✅ Done |
| 3 | BFF Server | ✅ Done |
| 4 | Frontend: Create Report Form | ✅ Done |
| 5 | Frontend: Report Folder Screen | ✅ Done |
| 6 | Frontend: Chat Interface | ✅ Done |
| 7 | End-to-End Smoke Test | ✅ Done |
