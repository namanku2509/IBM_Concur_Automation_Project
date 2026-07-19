/**
 * Issue a short-lived RS256 JWT for the embedded watsonx Orchestrate agent.
 *
 * WXO Embed Security requires the JWT to carry these standard claims:
 *   alg  RS256
 *   typ  JWT
 *   sub  IBM Cloud IAM user email / IBM ID  (WXO_USER_SUB or session user)
 *   iss  The issuer string registered in WXO Embed Security settings
 *   iat  Issued-at (Unix seconds)
 *   exp  Expiry (iat + TOKEN_LIFETIME_SECONDS)
 *   jti  A unique token ID so WXO can reject replay attacks
 *
 * The private key is loaded once at module startup and cached.  A synchronous
 * readFileSync on every request is safe in Node.js single-threaded model, but
 * caching avoids unnecessary I/O on every token refresh cycle (default: every
 * ~55 minutes when the widget detects expiry).
 */
const crypto = require('crypto');
const fs     = require('fs');
const path   = require('path');
const { randomUUID } = require('crypto');
const express = require('express');

const router = express.Router();
const TOKEN_LIFETIME_SECONDS = 60 * 60; // 1 hour

// ── Private key — resolved once at startup ────────────────────────────────────
// Search order: env var → workspace root → Orchestrate reference folder
const _localKeyPath     = path.resolve(__dirname, '../../../wxo_private.pem');
const _referenceKeyPath = path.resolve(__dirname, '../../../Orchestrate/wxo_private.pem');
const _defaultKeyPath   = fs.existsSync(_localKeyPath) ? _localKeyPath : _referenceKeyPath;

let _cachedPrivateKey = null;

function _loadPrivateKey() {
  if (_cachedPrivateKey) return _cachedPrivateKey;
  const keyPath = process.env.WXO_PRIVATE_KEY_PATH || _defaultKeyPath;
  _cachedPrivateKey = fs.readFileSync(keyPath, 'utf8');
  return _cachedPrivateKey;
}

// Pre-warm the key cache at startup so the first token request is instant
// and so a missing key file is detected immediately on server start.
try {
  _loadPrivateKey();
} catch (err) {
  console.warn('[wxo] WARNING: Could not load WXO private key at startup:', err.message);
  console.warn('[wxo] Ensure WXO_PRIVATE_KEY_PATH is set or wxo_private.pem is at the project root.');
}

// ── JWT helpers ───────────────────────────────────────────────────────────────
function _encode(value) {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

/**
 * Build and sign a short-lived RS256 JWT for the WXO embedded chat widget.
 *
 * @param {string} subject - IBM Cloud IAM email / IBM ID for this session
 * @returns {{ token: string, expiresAt: number }} signed JWT + expiry ms timestamp
 */
function createToken(subject) {
  const privateKey = _loadPrivateKey();
  const now = Math.floor(Date.now() / 1000);

  // WXO requires `iss` to match the Issuer URL configured in
  // WXO Console → Settings → Embed Security.
  // If WXO_ISSUER is not set we fall back to WXO_HOST_URL so existing
  // deployments work without adding another env var.
  const issuer = process.env.WXO_ISSUER || process.env.WXO_HOST_URL || '';

  const header  = _encode({ alg: 'RS256', typ: 'JWT' });
  const payload = _encode({
    sub: subject,
    iss: issuer,
    iat: now,
    exp: now + TOKEN_LIFETIME_SECONDS,
    jti: randomUUID(),               // unique token ID — prevents replay
  });

  const unsigned = `${header}.${payload}`;
  const signer   = crypto.createSign('RSA-SHA256');
  signer.update(unsigned);
  signer.end();

  return {
    token:     `${unsigned}.${signer.sign(privateKey, 'base64url')}`,
    expiresAt: (now + TOKEN_LIFETIME_SECONDS) * 1000,
  };
}

// ── Route ─────────────────────────────────────────────────────────────────────

router.get('/auth-token', (req, res) => {
  // Prefer authenticated session user; fall back to the static env-var subject
  // configured for single-user / demo deployments.
  const subject = req.session?.user?.id || process.env.WXO_USER_SUB;

  if (!subject) {
    return res.status(503).json({
      error: 'WXO_USER_SUB is not configured and no authenticated user is available.',
    });
  }

  try {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate');
    res.json(createToken(subject));
  } catch (err) {
    console.error('[wxo] Unable to create auth token:', err.message);
    res.status(503).json({ error: 'Unable to create watsonx Orchestrate auth token.' });
  }
});

module.exports = router;
