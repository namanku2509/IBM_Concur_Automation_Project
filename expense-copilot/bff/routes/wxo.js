/**
 * wxo.js
 * ------
 * Signs a short-lived RS256 JWT for the watsonx Orchestrate embedded chat widget.
 * The private key never leaves the server; the browser only ever sees the signed token.
 *
 * GET /api/wxo/auth-token
 *   Returns { token, expiresAt }
 *
 * Prerequisites:
 *   1. Generate an RSA-2048 keypair (see STARTUP.md).
 *   2. Place wxo_private.pem at the project root (or set WXO_PRIVATE_KEY_PATH).
 *   3. Paste wxo_public.pem into WXO console → Settings → Embed Security.
 *   4. Set WXO_USER_SUB=<your-ibm-email> in bff/.env.
 */
const crypto      = require('crypto');
const fs          = require('fs');
const path        = require('path');
const { randomUUID } = require('crypto');
const express     = require('express');

const router = express.Router();

const TOKEN_LIFETIME_SECONDS = 60 * 60;   // 1 hour

// Key search order: env override → workspace root → Orchestrate reference folder
const _localKeyPath     = path.resolve(__dirname, '../../../wxo_private.pem');
const _referenceKeyPath = path.resolve(__dirname, '../../../Orchestrate/wxo_private.pem');
const DEFAULT_PRIVATE_KEY_PATH = fs.existsSync(_localKeyPath) ? _localKeyPath : _referenceKeyPath;

// Pre-warm at startup so a missing key is caught immediately, not on first request
let _cachedPrivateKey = null;
try {
  _cachedPrivateKey = fs.readFileSync(process.env.WXO_PRIVATE_KEY_PATH || DEFAULT_PRIVATE_KEY_PATH, 'utf8');
} catch (err) {
  console.warn('[wxo] WARNING: Could not load WXO private key at startup:', err.message);
}

function base64Url(value) {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

function createToken(subject) {
  const privateKey = _cachedPrivateKey
    || fs.readFileSync(process.env.WXO_PRIVATE_KEY_PATH || DEFAULT_PRIVATE_KEY_PATH, 'utf8');

  const now    = Math.floor(Date.now() / 1000);
  // iss must match the Issuer URI registered in WXO Console → Settings → Embed Security
  const issuer = process.env.WXO_ISSUER || process.env.WXO_HOST_URL || '';

  const header  = base64Url({ alg: 'RS256', typ: 'JWT' });
  const payload = base64Url({
    sub: subject,
    iss: issuer,
    iat: now,
    exp: now + TOKEN_LIFETIME_SECONDS,
    jti: randomUUID(),   // unique token ID — WXO uses this to reject replay attacks
  });

  const unsignedToken = `${header}.${payload}`;
  const signer = crypto.createSign('RSA-SHA256');
  signer.update(unsignedToken);
  signer.end();

  return {
    token:     `${unsignedToken}.${signer.sign(privateKey, 'base64url')}`,
    expiresAt: (now + TOKEN_LIFETIME_SECONDS) * 1000,
  };
}

router.get('/auth-token', (req, res) => {
  const subject = req.session?.user?.id || process.env.WXO_USER_SUB;

  if (!subject) {
    return res.status(503).json({
      error: 'WXO_USER_SUB is not configured and no authenticated user is available.',
    });
  }

  try {
    res.set('Cache-Control', 'no-store');
    res.json(createToken(subject));
  } catch (err) {
    console.error('[wxo] Unable to create auth token:', err.message);
    res.status(503).json({ error: 'Unable to create watsonx Orchestrate auth token.' });
  }
});

module.exports = router;
