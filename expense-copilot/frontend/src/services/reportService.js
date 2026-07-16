import axios from 'axios';

// In production (VM), REACT_APP_API_URL is set to http://169.60.30.246/api
// In local dev it falls back to localhost:4000/api
const BFF_BASE = process.env.REACT_APP_API_URL || 'http://localhost:4000/api';

/**
 * Creates a new expense report folder via the BFF.
 * @param {Object} fields - { reportName, businessPurpose, policy, reportCategory }
 * @returns {Object} - { reportId, status, createdAt }
 */
export async function createReport(fields) {
  const response = await axios.post(`${BFF_BASE}/report`, fields);
  return response.data;
}

/**
 * Fetches available corporate card transactions for a report.
 * @param {string} reportId
 * @returns {Object} - { reportId, totalCount, transactions[] }
 */
export async function getTransactions(reportId) {
  const response = await axios.get(`${BFF_BASE}/report/${reportId}/transactions`);
  return response.data;
}

/**
 * Uploads receipt files to be processed by Layer 2.
 * @param {string} reportId
 * @param {FileList} files
 * @returns {Object} - { processed, matched, unmatched, expenses[], warnings[] }
 */
export async function processReceipts(reportId, files) {
  const form = new FormData();
  Array.from(files).forEach(file => form.append('files', file));
  const response = await axios.post(`${BFF_BASE}/report/${reportId}/receipts`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // 11 min — slightly longer than BFF's 10 min to Docling so BFF timeout error
    // reaches the frontend first (rather than a raw network timeout).
    timeout: 660000,
  });
  return response.data;
}

/**
 * Submits the completed expense report to Layer 3.
 * @param {string} reportId
 * @returns {Object} - { status, confirmationId, warnings[] }
 */
export async function submitReport(reportId) {
  const response = await axios.post(`${BFF_BASE}/report/${reportId}/submit`);
  return response.data;
}

/**
 * Fetches current report folder state from BFF.
 * @param {string} reportId
 * @returns {Object} - full report folder object
 */
export async function getReport(reportId) {
  const response = await axios.get(`${BFF_BASE}/report/${reportId}`);
  return response.data;
}
