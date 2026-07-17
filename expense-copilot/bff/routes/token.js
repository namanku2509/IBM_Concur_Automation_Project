/**
 * token.js
 * --------
 * BFF proxy that exchanges an IBM Cloud API key for a short-lived IAM bearer
 * token. The frontend calls this instead of hitting IAM directly, so the API
 * key never leaves the server.
 *
 * GET /api/token
 *   Returns { access_token, expiry } on success.
 *   Returns 500 if WXO_IBM_API_KEY is not set or IAM exchange fails.
 *
 * IAM token endpoint:
 *   POST https://iam.cloud.ibm.com/identity/token
 *   body: grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey=<key>
 *   Returns { access_token, expiration, ... }
 */
const express = require('express');
const axios   = require('axios');
const router  = express.Router();

const IAM_URL = 'https://iam.cloud.ibm.com/identity/token';

// Cache the token in memory — IAM tokens last ~1 hour, refresh 5 min early
let cached = null;  // { access_token, expiry }

router.get('/', async (req, res) => {
  const apiKey = process.env.WXO_IBM_API_KEY || '';
  if (!apiKey) {
    return res.status(500).json({ error: 'WXO_IBM_API_KEY not set in BFF .env' });
  }

  // Return cached token if still valid
  if (cached && cached.expiry > Date.now() + 5 * 60 * 1000) {
    return res.json({ access_token: cached.access_token, expiry: cached.expiry });
  }

  try {
    const response = await axios.post(
      IAM_URL,
      new URLSearchParams({
        grant_type: 'urn:ibm:params:oauth:grant-type:apikey',
        apikey: apiKey,
      }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, timeout: 10000 }
    );

    const { access_token, expiration } = response.data;
    // IAM returns expiration as Unix seconds
    cached = { access_token, expiry: expiration * 1000 };
    res.json({ access_token, expiry: cached.expiry });
  } catch (err) {
    const detail = err.response?.data || err.message;
    console.error('[token] IAM exchange failed:', detail);
    res.status(502).json({ error: 'Failed to get IAM token', detail });
  }
});

module.exports = router;
