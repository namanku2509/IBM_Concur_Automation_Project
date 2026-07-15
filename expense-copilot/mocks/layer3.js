const express = require('express');
const router = express.Router();
const transactions = require('./data/transactions.json');
const employees = require('./data/employees.json');
const policies = require('./data/policies.json');

// In-memory store for created reports (simulates Concur DB)
const reports = {};

// ─────────────────────────────────────────────
// GET /employees/:empId
// Returns employee profile
// ─────────────────────────────────────────────
router.get('/employees/:empId', (req, res) => {
  const employee = employees.find(e => e.employeeId === req.params.empId);
  if (!employee) {
    return res.status(404).json({ error: 'Employee not found', employeeId: req.params.empId });
  }
  res.json(employee);
});

// ─────────────────────────────────────────────
// GET /employees/:empId/transactions
// Returns corporate card transactions for an employee
// Optionally filtered by ?policy= and ?category=
// ─────────────────────────────────────────────
router.get('/employees/:empId/transactions', (req, res) => {
  const { empId } = req.params;
  const { policy, category } = req.query;

  const employee = employees.find(e => e.employeeId === empId);
  if (!employee) {
    return res.status(404).json({ error: 'Employee not found', employeeId: empId });
  }

  let result = transactions.filter(t => t.employeeId === empId);

  if (policy) {
    result = result.filter(t => t.policy === policy);
  }
  if (category) {
    result = result.filter(t => t.category === category);
  }

  res.json({
    employeeId: empId,
    totalCount: result.length,
    transactions: result
  });
});

// ─────────────────────────────────────────────
// POST /reports
// Creates a new expense report container
// ─────────────────────────────────────────────
router.post('/reports', (req, res) => {
  const { employeeId, reportName, businessPurpose, policy, reportCategory, reportId: providedId } = req.body;

  if (!employeeId || !reportName || !businessPurpose || !policy || !reportCategory) {
    return res.status(422).json({
      error: 'Missing mandatory fields',
      required: ['employeeId', 'reportName', 'businessPurpose', 'policy', 'reportCategory']
    });
  }

  const employee = employees.find(e => e.employeeId === employeeId);
  if (!employee) {
    return res.status(404).json({ error: 'Employee not found', employeeId });
  }

  // Use the BFF-provided reportId if given, otherwise generate one
  const reportId = providedId || `RPT-${Date.now()}`;
  reports[reportId] = {
    reportId,
    employeeId,
    reportName,
    businessPurpose,
    policy,
    reportCategory,
    status: 'DRAFT',
    createdAt: new Date().toISOString(),
    expenses: []
  };

  res.status(201).json({
    reportId,
    status: 'DRAFT',
    createdAt: reports[reportId].createdAt
  });
});

// ─────────────────────────────────────────────
// GET /reports/:reportId
// Returns report status and summary
// ─────────────────────────────────────────────
router.get('/reports/:reportId', (req, res) => {
  const report = reports[req.params.reportId];
  if (!report) {
    return res.status(404).json({ error: 'Report not found', reportId: req.params.reportId });
  }
  res.json(report);
});

// ─────────────────────────────────────────────
// POST /reports/:reportId/submit
// Accepts the final report payload and persists it
// Simulates Concur business validation before acceptance
// ─────────────────────────────────────────────
router.post('/reports/:reportId/submit', (req, res) => {
  const { reportId } = req.params;
  const { employeeId, expenses } = req.body;

  // Step 1 — Validate report exists
  if (!reports[reportId]) {
    return res.status(404).json({ error: 'Report not found', reportId });
  }

  const report = reports[reportId];

  // Step 2 — Validate report is still editable
  if (report.status === 'SUBMITTED') {
    return res.status(409).json({ error: 'Report already submitted', reportId });
  }

  // Step 3 — Validate employee
  const employee = employees.find(e => e.employeeId === employeeId);
  if (!employee) {
    return res.status(404).json({ error: 'Employee not found', employeeId });
  }

  // Step 4 — Load applicable policy
  const policy = policies.find(p => p.name === report.policy);
  const warnings = [];
  const errors = [];

  // Step 5 — Validate each expense against policy
  if (expenses && expenses.length > 0) {
    expenses.forEach(expense => {
      // Mandatory field check
      if (!expense.vendor) errors.push({ expenseId: expense.expenseId, code: 'MISSING_VENDOR', message: 'Vendor name is required', severity: 'ERROR' });
      if (!expense.amount) errors.push({ expenseId: expense.expenseId, code: 'MISSING_AMOUNT', message: 'Amount is required', severity: 'ERROR' });
      if (!expense.transactionDate) errors.push({ expenseId: expense.expenseId, code: 'MISSING_DATE', message: 'Transaction date is required', severity: 'ERROR' });

      if (policy) {
        // Hotel nightly limit
        if (expense.expenseType === 'HOTEL' && expense.hotelDetails) {
          const nightlyRate = expense.hotelDetails.nightlyRate || (expense.amount / (expense.hotelDetails.numNights || 1));
          if (nightlyRate > policy.limits.HOTEL.nightlyLimit) {
            warnings.push({
              expenseId: expense.expenseId,
              code: 'POLICY_HOTEL_LIMIT',
              message: `Hotel nightly rate ${expense.currency} ${nightlyRate} exceeds policy limit of ${expense.currency} ${policy.limits.HOTEL.nightlyLimit}`,
              severity: 'WARNING'
            });
          }
        }

        // Meal limit
        if (expense.expenseType === 'MEAL' && expense.amount > policy.limits.MEAL.perMealLimit) {
          warnings.push({
            expenseId: expense.expenseId,
            code: 'POLICY_MEAL_LIMIT',
            message: `Meal expense ${expense.currency} ${expense.amount} exceeds policy limit of ${expense.currency} ${policy.limits.MEAL.perMealLimit}`,
            severity: 'WARNING'
          });
        }

        // Taxi limit
        if (expense.expenseType === 'TAXI' && expense.amount > policy.limits.TAXI.perRideLimit) {
          warnings.push({
            expenseId: expense.expenseId,
            code: 'POLICY_TAXI_LIMIT',
            message: `Taxi expense ${expense.currency} ${expense.amount} exceeds policy limit of ${expense.currency} ${policy.limits.TAXI.perRideLimit}`,
            severity: 'WARNING'
          });
        }

        // Currency check
        if (!policy.allowedCurrencies.includes(expense.currency)) {
          warnings.push({
            expenseId: expense.expenseId,
            code: 'POLICY_CURRENCY',
            message: `Currency ${expense.currency} is not allowed under policy ${report.policy}`,
            severity: 'WARNING'
          });
        }
      }
    });
  }

  // Step 6 — Return errors without saving if hard errors exist
  if (errors.length > 0) {
    return res.status(422).json({
      reportId,
      status: 'VALIDATION_FAILED',
      errors,
      warnings
    });
  }

  // Step 7 — Persist (update in-memory store)
  report.status = 'SUBMITTED';
  report.submittedAt = new Date().toISOString();
  report.expenses = expenses || [];

  const confirmationId = `CNF-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${Math.floor(Math.random() * 1000).toString().padStart(3, '0')}`;

  // Step 8 — Return Concur-style response
  res.status(200).json({
    reportId,
    status: 'SUBMITTED',
    confirmationId,
    submittedAt: report.submittedAt,
    expenseCount: (expenses || []).length,
    warnings,
    validationSummary: {
      errors: 0,
      warnings: warnings.length,
      info: 0
    }
  });
});

// ─────────────────────────────────────────────
// GET /policies/:policyId
// Returns a specific policy's rules
// ─────────────────────────────────────────────
router.get('/policies/:policyId', (req, res) => {
  const policy = policies.find(p => p.policyId === req.params.policyId || p.name === req.params.policyId);
  if (!policy) {
    return res.status(404).json({ error: 'Policy not found', policyId: req.params.policyId });
  }
  res.json(policy);
});

// Health check
router.get('/health', (req, res) => {
  res.json({ layer: 'Layer 3 — SAP Concur Stub Mock', status: 'ok' });
});

module.exports = router;
