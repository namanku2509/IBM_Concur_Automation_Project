/**
 * Layer 2 service — proxies calls to the AI Middleware (or mock).
 * Handles multipart file forwarding from the browser upload
 * through the BFF to Layer 2 without touching the file bytes.
 */
const axios = require('axios');
const FormData = require('form-data');
const { LAYER2_BASE_URL } = require('../config');

async function processReceipts(reportId, employeeId, files, paymentHint = 'card') {
  const form = new FormData();
  form.append('report_id', reportId);
  form.append('employee_id', employeeId);
  form.append('payment_hint', paymentHint);

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
