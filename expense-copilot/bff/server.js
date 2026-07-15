const express = require('express');
const cors = require('cors');
const session = require('express-session');
require('dotenv').config();

const reportRoutes = require('./routes/report');

const app = express();

const ALLOWED_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:3000';
app.use(cors({ origin: ALLOWED_ORIGIN, credentials: true }));
app.use(express.json());
app.use(session({
  secret: process.env.SESSION_SECRET || 'expense-copilot-secret',
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false }
}));

app.use('/api/report', reportRoutes);

app.get('/health', (req, res) => {
  res.json({ service: 'BFF Server', status: 'ok' });
});

// Also expose health at /api/health so nginx proxy_pass /api/ → BFF works
app.get('/api/health', (req, res) => {
  res.json({ service: 'BFF Server', status: 'ok' });
});

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => {
  console.log(`BFF server running on http://localhost:${PORT}`);
});
