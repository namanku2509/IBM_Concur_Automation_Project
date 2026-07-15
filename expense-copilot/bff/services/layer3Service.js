/**
 * Layer 3 service — proxies calls to the SAP Concur Stub.
 * All Layer 3 URLs come from config so swapping mock → real
 * requires only an environment variable change.
 *
 * Actual Layer 3 API (concur-stub) contract:
 *   POST   /api/v4/expense-reports                        — create shell report
 *   GET    /api/v4/card-transactions?employeeId=<id>      — list card transactions
 *   POST   /api/v4/expense-reports/:id/expenses           — bulk submit expenses
 *   PATCH  /api/v4/expense-reports/:id/submit             — transition to SUBMITTED
 */
const axios = require('axios');
const { LAYER3_BASE_URL } = require('../config');

const L3 = axios.create({ baseURL: LAYER3_BASE_URL, timeout: 30000 });

/**
 * Create a shell expense report in Layer 3.
 * Layer 3 expects camelCase aliases: reportId, employeeId, reportName,
 * businessPurpose, travelPolicy, expenseCategory.
 */
async function createReport(reportId, fields) {
  const response = await L3.post('/api/v4/expense-reports', {
    reportId,
    employeeId: fields.employeeId,
    reportName: fields.reportName,
    businessPurpose: fields.businessPurpose,
    travelPolicy: fields.policy,           // BFF uses "policy"; L3 alias is "travelPolicy"
    expenseCategory: fields.reportCategory, // BFF uses "reportCategory"; L3 alias is "expenseCategory"
  });
  return response.data;
}

/**
 * Fetch available corporate card transactions for an employee.
 * Layer 3 returns { employeeId, transactions[], total }.
 * The BFF normalises this to { transactions[], totalCount }.
 */
async function getTransactions(employeeId, { policy } = {}) {
  const response = await L3.get('/api/v4/card-transactions', {
    params: { employeeId },
  });
  const data = response.data;
  return {
    transactions: data.transactions || [],
    totalCount: data.total ?? (data.transactions || []).length,
  };
}

/**
 * Bulk-submit all processed expenses to Layer 3.
 * Layer 3 path: POST /api/v4/expense-reports/:id/expenses
 * Expects envelope: { employeeId, expenses: [...] }
 * Returns ExpensesSubmitResponse: { reportId, status, warnings, processedExpenses, summary }
 */
async function submitExpenses(reportId, employeeId, expenses) {
  const response = await L3.post(
    `/api/v4/expense-reports/${reportId}/expenses`,
    { employeeId, expenses }
  );
  return response.data;
}

/**
 * Transition the report from DRAFT/MANUAL_REVIEW → SUBMITTED.
 * Layer 3 path: PATCH /api/v4/expense-reports/:id/submit
 * Returns StatusResponse: { reportId, status, message }
 */
async function submitReport(reportId) {
  const response = await L3.patch(`/api/v4/expense-reports/${reportId}/submit`);
  return response.data;
}

module.exports = { createReport, getTransactions, submitExpenses, submitReport };
