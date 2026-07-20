/**
 * Layer 2 service — proxies calls to the AI Middleware (or mock).
 * Handles multipart file forwarding from the browser upload
 * through the BFF to Layer 2 without touching the file bytes.
 */
const axios = require('axios');
const FormData = require('form-data');
const { LAYER2_BASE_URL } = require('../config');

async function processReceipts(reportId, employeeId, files, paymentHint = 'card', allowedTxnIds = null) {
  const form = new FormData();
  form.append('report_id', reportId);
  form.append('employee_id', employeeId);
  form.append('payment_hint', paymentHint);

  // When the user pre-selected specific transactions, tell Layer 2 to match
  // ONLY against those IDs. Any receipt that would match a txn outside this
  // set must be returned as unmatched.
  if (allowedTxnIds && Array.isArray(allowedTxnIds) && allowedTxnIds.length > 0) {
    form.append('allowed_txn_ids', JSON.stringify(allowedTxnIds));
  }

  files.forEach(file => {
    form.append('files', file.buffer, {
      filename: file.originalname,
      contentType: file.mimetype
    });
  });

  const response = await axios.post(
    `${LAYER2_BASE_URL}/pipeline/run`,
    form,
    { headers: form.getHeaders(), timeout: 600000 }   // 10 min — Docling OCR is slow on CPU-only VM
  );
  return response.data;
}

module.exports = { processReceipts };
