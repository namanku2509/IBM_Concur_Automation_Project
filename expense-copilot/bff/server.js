const express = require('express');
const path    = require('path');
const cors    = require('cors');
const session = require('express-session');

// Primary .env — lives at expense-copilot/bff/.env in production.
require('dotenv').config();

// Fallback: load the Orchestrate reference .env when the WXO vars are not yet
// copied into the local bff/.env.  Only applied when WXO_ORCHESTRATION_ID is
// absent so the local file always wins once the operator sets it up.
if (!process.env.WXO_ORCHESTRATION_ID) {
  const orchestrateEnv = path.resolve(__dirname, '../../Orchestrate/expense-copilot/bff/.env');
  require('dotenv').config({ path: orchestrateEnv, override: false });
}

const reportRoutes = require('./routes/report');
const travelRoutes = require('./routes/travel');
const chatRoutes   = require('./routes/chat');
const wxoRoutes    = require('./routes/wxo');

const app = express();

// ── CORS ──────────────────────────────────────────────────────────────────────
const ALLOWED_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:3000';
app.use(cors({ origin: ALLOWED_ORIGIN, credentials: true }));

// ── Body parsing ──────────────────────────────────────────────────────────────
app.use(express.json());

// ── Session ───────────────────────────────────────────────────────────────────
// cookie.secure must be true when served over HTTPS (production / nginx TLS).
// In local dev (http://localhost) it must be false — otherwise the browser
// drops the Set-Cookie header and session auth breaks.
const isProduction = process.env.NODE_ENV === 'production';
app.use(session({
  secret:            process.env.SESSION_SECRET || 'expense-copilot-secret',
  resave:            false,
  saveUninitialized: true,
  cookie: {
    secure:   isProduction,   // true in prod (HTTPS), false in local dev
    httpOnly: true,           // prevent JS access to the session cookie
    sameSite: 'lax',          // CSRF mitigation
  },
}));

// ── Routes ────────────────────────────────────────────────────────────────────
app.use('/api/report', reportRoutes);
app.use('/api/travel', travelRoutes);
app.use('/api/chat',   chatRoutes);
app.use('/api/wxo',    wxoRoutes);

// Standalone travel workspace — served from /travel (same-origin for the BFF).
app.use('/travel', express.static(path.resolve(__dirname, '../../travel-claim-dashboard')));

// ── Health checks ─────────────────────────────────────────────────────────────
app.get('/health', (_req, res) => {
  res.json({ service: 'BFF Server', status: 'ok' });
});

// /api/health so nginx proxy_pass /api/ → BFF health check works correctly.
app.get('/api/health', (_req, res) => {
  res.json({ service: 'BFF Server', status: 'ok' });
});

// ── Start ─────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 4000;
app.listen(PORT, '127.0.0.1', () => {
  console.log(`BFF server running on http://127.0.0.1:${PORT}`);
});
