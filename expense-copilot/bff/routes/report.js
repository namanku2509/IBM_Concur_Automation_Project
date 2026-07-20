const express = require('express');
const multer = require('multer');
const { v4: uuidv4 } = require('uuid');
const router = express.Router();

const reportStore = require('../session/reportStore');
const layer3 = require('../services/layer3Service');
const layer2 = require('../services/layer2Service');
const { getVisibleTransactions } = require('../services/reportSelectionService');

// Accept files in memory so we can forward buffers to Layer 2
const upload = multer({ storage: multer.memoryStorage() });

// Default employee — overridden by the employeeId field sent from the frontend
const DEFAULT_EMPLOYEE_ID = 'EMP001';

// ─────────────────────────────────────────────────────────────────────────────
// Helper: Normalise a ReceiptResult from Layer 2 pipeline into a consistent
// shape for the session store and the frontend.
//
// Layer 2 returns camelCase from Pydantic (by_alias):
//   expenseType, transactionDate, paymentType, matchedTxnId, matchConfidence,
//   expenseId, hotelDetail, airfareDetail, taxiDetail, mealDetail, ...
//
// We keep the camelCase names as-is so the frontend can consume them directly.
// ─────────────────────────────────────────────────────────────────────────────
function normaliseExpense(r) {
  return {
    filename:        r.filename,
    status:          r.status,
    errorMessage:    r.error_message ?? r.errorMessage ?? null,
    expenseType:     r.expense_type    ?? r.expenseType,
    vendor:          r.vendor,
    amount:          r.amount,
    currency:        r.currency        ?? 'INR',
    transactionDate: r.transaction_date ?? r.transactionDate,
    city:            r.city,
    paymentType:     r.payment_type    ?? r.paymentType,
    matchedTxnId:    r.matched_txn_id  ?? r.matchedTxnId   ?? null,
    matchConfidence: r.match_confidence ?? r.matchConfidence ?? 0,
    expenseId:       r.expense_id      ?? r.expenseId       ?? null,
    fileHash:        r.file_hash       ?? r.fileHash        ?? null,
    warnings:        r.warnings        ?? [],
    // Nested detail objects
    hotelDetail:        r.hotel_detail      ?? r.hotelDetail      ?? null,
    airfareDetail:      r.airfare_detail    ?? r.airfareDetail    ?? null,
    taxiDetail:         r.taxi_detail       ?? r.taxiDetail       ?? null,
    mealDetail:         r.meal_detail       ?? r.mealDetail       ?? null,
    registrationDetail: r.registration_detail ?? r.registrationDetail ?? null,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: Convert a normalised expense into the Layer 3 ExpenseInput shape.
// Layer 3 expects camelCase aliases (SAP Concur v4 convention).
//
// Notes:
//   - expense_type MEALS (Layer 2 internal) → MEAL (Layer 3 enum)
//   - HOTEL needs itemization[] built from hotelDetail
//   - FLIGHT needs airfareDetail → airfareDetail (already camelCase)
//   - Only city, vendor, amount, currency, transactionDate, paymentType are
//     mandatory; all detail sub-objects are optional on the Layer 3 side.
// ─────────────────────────────────────────────────────────────────────────────
function toL3ExpenseInput(exp) {
  // Map MEALS → MEAL to match Layer 3 ExpenseType enum
  const expenseType = (exp.expenseType === 'MEALS') ? 'MEAL' : exp.expenseType;

  // Layer 3 PaymentType enum: CORPORATE_CARD | PERSONAL_CASH | CORPORATE_CASH
  // Layer 2 returns OUT_OF_POCKET for unmatched — map it to PERSONAL_CASH
  const rawPayment = exp.paymentType || 'PERSONAL_CASH';
  const paymentType = (rawPayment === 'OUT_OF_POCKET') ? 'PERSONAL_CASH' : rawPayment;

  const input = {
    expenseType,
    vendor:          exp.vendor   || 'UNKNOWN',
    amount:          exp.amount,
    currency:        exp.currency || 'INR',
    transactionDate: exp.transactionDate || new Date().toISOString().split('T')[0],
    city:            exp.city     || 'UNKNOWN',
    paymentType,
  };

  // Build itemization for HOTEL — ALWAYS send itemization, even when hotelDetail is null.
  // L3 schema REQUIRES itemization for HOTEL (ITEMIZATION_REQUIRED pre-flight check).
  // When hotelDetail is missing (OCR failed to extract dates), fall back to 1 night at full amount.
  if (expenseType === 'HOTEL') {
    const hd = exp.hotelDetail || {};
    const nights  = hd.num_nights   ?? hd.numNights   ?? 1;
    const rate    = hd.nightly_rate ?? hd.nightlyRate ?? exp.amount;
    const taxes   = hd.tax_amount   ?? hd.taxAmount   ?? 0;
    const checkIn = hd.check_in_date ?? hd.checkInDate ?? input.transactionDate;
    const itemization = [];
    for (let i = 0; i < nights; i++) {
      // Guard against null/invalid dates — fall back to today if nothing was extracted
      const baseRaw  = checkIn || new Date().toISOString().split('T')[0];
      const baseDate = new Date(baseRaw);
      const safeBase = isNaN(baseDate.getTime()) ? new Date() : baseDate;
      safeBase.setDate(safeBase.getDate() + i);
      itemization.push({
        nightDate: safeBase.toISOString().split('T')[0],
        roomRate:  rate,
        taxes:     parseFloat((taxes / nights).toFixed(2)),
      });
    }
    input.itemization = itemization;
  }

  // Build airfareDetail for FLIGHT — ALWAYS send, even when L2 didn't extract fields.
  // L3 accepts all-default values (origin/destination default to "UNKNOWN").
  if (expenseType === 'FLIGHT') {
    const ad = exp.airfareDetail || {};
    const rawClass = (ad.travel_class ?? ad.travelClass ?? 'ECONOMY').toUpperCase();
    const validClasses = ['ECONOMY', 'BUSINESS', 'FIRST'];
    input.airfareDetail = {
      origin:       ad.origin       ?? 'UNKNOWN',
      destination:  ad.destination  ?? 'UNKNOWN',
      travelClass:  validClasses.includes(rawClass) ? rawClass : 'ECONOMY',
      flightNumber: ad.flight_number ?? ad.flightNumber ?? null,
      ticketNumber: ad.ticket_number ?? ad.ticketNumber ?? null,
    };
  }

  // Build taxiDetail for TAXI — ALWAYS send with UNKNOWN defaults when L2 didn't extract locations.
  if (expenseType === 'TAXI') {
    const td = exp.taxiDetail || {};
    input.taxiDetail = {
      fromLocation: td.from_location ?? td.fromLocation ?? 'UNKNOWN',
      toLocation:   td.to_location   ?? td.toLocation   ?? 'UNKNOWN',
      distanceKm:   td.distance_km   ?? td.distanceKm   ?? null,
    };
  }

  // Build mealDetail for MEAL
  if (expenseType === 'MEAL' && exp.mealDetail) {
    const md = exp.mealDetail;
    const rawMealType = (md.meal_type ?? md.mealType ?? 'MEAL').toUpperCase();
    const validMealTypes = ['BREAKFAST', 'LUNCH', 'DINNER', 'SNACK', 'MEAL'];
    input.mealDetail = {
      mealType:  validMealTypes.includes(rawMealType) ? rawMealType : 'MEAL',
      attendees: md.num_attendees ?? md.attendees ?? 1,
    };
  }

  return input;
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /api/report
// Creates a new report folder in BFF session state AND registers
// it in Layer 3 so the submit step can find it later.
// ─────────────────────────────────────────────────────────────────────────────
router.post('/', async (req, res) => {
  const { employeeId, reportName, businessPurpose, policy, reportCategory, selectedTxnIds } = req.body;

  // Validate mandatory fields
  const missing = [];
  if (!reportName)      missing.push('reportName');
  if (!businessPurpose) missing.push('businessPurpose');
  if (!policy)          missing.push('policy');
  if (!reportCategory)  missing.push('reportCategory');

  if (missing.length > 0) {
    return res.status(422).json({ error: 'Missing mandatory fields', missing });
  }

  const reportId = `RPT-${uuidv4().slice(0, 8).toUpperCase()}`;

  // Use employeeId from request body, fallback to default
  const resolvedEmployeeId = employeeId || DEFAULT_EMPLOYEE_ID;

  try {
    // Register in Layer 3 so submit can find it
    await layer3.createReport(reportId, {
      employeeId: resolvedEmployeeId,
      reportName,
      businessPurpose,
      policy,
      reportCategory,
    });
  } catch (err) {
    const detail = err.response?.data || err.message;
    return res.status(502).json({ error: 'Failed to register report in Layer 3', detail });
  }

  let parsedSelectedTxnIds = null;
  if (selectedTxnIds) {
    try {
      parsedSelectedTxnIds = JSON.parse(selectedTxnIds);
    } catch (_) {
      parsedSelectedTxnIds = null;
    }
  }

  const folder = reportStore.create(reportId, {
    employeeId: resolvedEmployeeId,
    reportName,
    businessPurpose,
    policy,
    reportCategory,
    selectedTxnIds: parsedSelectedTxnIds,
  });

  res.status(201).json({
    reportId: folder.reportId,
    status:    folder.status,
    createdAt: folder.createdAt,
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/report/all?employeeId=EMP001
// Returns all report folders for the given employee (or all if omitted).
// Must be defined BEFORE /:reportId so "all" is not treated as a reportId.
// ─────────────────────────────────────────────────────────────────────────────
router.get('/all', (req, res) => {
  const { employeeId } = req.query;
  const reports = reportStore.getAll(employeeId || null);
  // Strip processedHashes (Set — not JSON-serialisable) before sending
  const safe = reports.map(r => {
    const { processedHashes, ...rest } = r;
    return rest;
  });
  res.json(safe);
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/report/:reportId
// Returns the current state of the report folder from session.
// ─────────────────────────────────────────────────────────────────────────────
router.get('/:reportId', (req, res) => {
  const folder = reportStore.get(req.params.reportId);
  if (!folder) {
    return res.status(404).json({ error: 'Report not found', reportId: req.params.reportId });
  }
  res.json(folder);
});

// ─────────────────────────────────────────────────────────────────────────────
// GET /api/report/:reportId/transactions
// Fetches available corporate card transactions from Layer 3.
// Layer 3 returns { employeeId, transactions[], total }.
// We normalise to { reportId, totalCount, transactions[] }.
// ─────────────────────────────────────────────────────────────────────────────
router.get('/:reportId/transactions', async (req, res) => {
  const folder = reportStore.get(req.params.reportId);
  if (!folder) {
    return res.status(404).json({ error: 'Report not found', reportId: req.params.reportId });
  }

  try {
    const data = await layer3.getTransactions(folder.employeeId, { policy: folder.policy });
    const { transactions: visibleTransactions, selectedTxnIds } = getVisibleTransactions(
      data.transactions,
      folder,
      req.query.txnIds,
    );

    const shouldPersistSelection = selectedTxnIds !== null && (
      folder.selectedTxnIds === undefined || folder.selectedTxnIds === null || req.query.txnIds
    );

    reportStore.update(folder.reportId, {
      availableExpenses: visibleTransactions,
      ...(shouldPersistSelection ? { selectedTxnIds } : {}),
      status: 'EXPENSES_LOADED',
    });

    res.json({
      reportId:   folder.reportId,
      totalCount: visibleTransactions.length,
      transactions: visibleTransactions,
    });
  } catch (err) {
    const status  = err.response?.status || 502;
    const message = err.response?.data?.detail || err.response?.data?.error || 'Failed to fetch transactions from Layer 3';
    res.status(status).json({ error: message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// POST /api/report/:reportId/receipts
// Accepts uploaded receipt files from the browser.
// Forwards them to Layer 2 for OCR + matching.
// Layer 2 returns PipelineResult: { report_id, processed, matched, unmatched,
//   errors, results: ReceiptResult[], summary }.
// Stores returned expenses + warnings in the report folder.
// ─────────────────────────────────────────────────────────────────────────────
router.post('/:reportId/receipts', upload.array('files'), async (req, res) => {
  const folder = reportStore.get(req.params.reportId);
  if (!folder) {
    return res.status(404).json({ error: 'Report not found', reportId: req.params.reportId });
  }

  const files = req.files || [];
  if (files.length === 0) {
    return res.status(422).json({ error: 'No receipt files provided' });
  }

  // ── BFF-level duplicate detection ────────────────────────────────────────
  // Hash every uploaded file and reject any that were already processed in
  // this report session, regardless of which drop zone they came from.
  const crypto = require('crypto');
  const duplicateFilenames = [];
  const duplicateExpenses = [];
  const uniqueFiles = [];
  for (const file of files) {
    const hash = crypto.createHash('sha256').update(file.buffer).digest('hex');
    if (reportStore.hasHash(folder.reportId, hash)) {
      duplicateFilenames.push(file.originalname);
      const originalExpense = (folder.processedExpenses || []).find(expense => expense.fileHash === hash);
      duplicateExpenses.push({
        ...(originalExpense || {}),
        filename: file.originalname,
        fileHash: hash,
        status: 'duplicate',
      });
    } else {
      file._sha256 = hash;   // stash for registration after success
      uniqueFiles.push(file);
    }
  }

  if (uniqueFiles.length === 0) {
    return res.json({
      reportId: folder.reportId,
      processed: duplicateExpenses.length,
      matched: 0,
      unmatched: 0,
      expenses: duplicateExpenses,
      warnings: duplicateFilenames.map(name => ({
        code: 'DUPLICATE_RECEIPT',
        severity: 'WARNING',
        message: `${name}: Already added to this report — skipped.`,
      })),
      validationSummary: null,
    });
  }

  reportStore.setStatus(folder.reportId, 'PROCESSING');

  try {
    // paymentHint comes from the frontend form field — 'card' or 'cash'
    const paymentHint = req.body?.paymentHint || 'card';
    // Pass the pre-selected txn IDs so Layer 2 only matches against those.
    // null means no restriction (all available txns are candidates).
    const allowedTxnIds = folder.selectedTxnIds || null;
    const data = await layer2.processReceipts(folder.reportId, folder.employeeId, uniqueFiles, paymentHint, allowedTxnIds);

    // Layer 2 returns results[] not expenses[]
    const rawResults = data.results || data.expenses || [];
    const processedExpenses = rawResults.map(normaliseExpense).map(e => {
      // Downgrade a "success" result that has no usable fields — the LLM and
      // heuristic both failed to extract anything meaningful. Treat it as an
      // error so a blank row never appears in the expenses table.
      if (
        e.status === 'success' &&
        (!e.amount || Number(e.amount) <= 0) &&
        (!e.vendor || !String(e.vendor).trim())
      ) {
        return {
          ...e,
          status: 'error',
          errorMessage: e.errorMessage || 'Could not extract expense fields from this receipt (amount and vendor missing). The PDF may be a scanned image or the text is not machine-readable.',
        };
      }
      return e;
    });

    // Register hashes for every successfully processed receipt so they can't
    // be re-uploaded in a subsequent card or cash drop zone call.
    for (const file of uniqueFiles) {
      const result = rawResults.find(r => r.filename === file.originalname);
      if (result && result.status === 'success') {
        reportStore.addHash(folder.reportId, file._sha256);
      }
    }

    // Build warnings — include duplicate-skipped notice if any
    const allWarnings = [
      ...processedExpenses.flatMap(e => e.warnings || []),
      ...processedExpenses
        .filter(e => e.status === 'error')
        .map(e => ({
          code: 'RECEIPT_PROCESSING_FAILED',
          severity: 'ERROR',
          message: `${e.filename}: ${e.errorMessage || 'Layer 2 could not process this receipt.'}`,
        })),
      ...duplicateFilenames.map(name => ({
        code: 'DUPLICATE_RECEIPT',
        severity: 'WARNING',
        message: `${name}: Already added to this report — skipped.`,
      })),
    ];

    reportStore.update(folder.reportId, {
      processedExpenses: [...(folder.processedExpenses || []), ...processedExpenses],
      warnings: [...(folder.warnings || []), ...allWarnings],
      status: 'REVIEW',
    });

    res.json({
      reportId:          folder.reportId,
      processed:         (data.processed  ?? rawResults.length) + duplicateExpenses.length,
      matched:           data.matched    ?? 0,
      unmatched:         data.unmatched  ?? rawResults.length,
      expenses:          [...processedExpenses, ...duplicateExpenses],
      warnings:          allWarnings,
      validationSummary: data.summary    ?? null,
    });
  } catch (err) {
    reportStore.setStatus(folder.reportId, 'EXPENSES_LOADED');
    const status  = err.response?.status || 502;
    const message = err.response?.data?.detail || err.response?.data?.error || 'Failed to process receipts via Layer 2';
    res.status(status).json({ error: message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// POST /api/report/:reportId/submit
// Two-step submit to Layer 3:
//   Step 1 — POST /api/v4/expense-reports/:id/expenses  (bulk expense ingestion)
//   Step 2 — PATCH /api/v4/expense-reports/:id/submit   (status transition)
// Updates folder status to SUBMITTED on success.
// ─────────────────────────────────────────────────────────────────────────────
router.post('/:reportId/submit', async (req, res) => {
  const folder = reportStore.get(req.params.reportId);
  if (!folder) {
    return res.status(404).json({ error: 'Report not found', reportId: req.params.reportId });
  }

  if (folder.status === 'SUBMITTED') {
    return res.status(409).json({ error: 'Report already submitted', reportId: folder.reportId });
  }

  // Policy exception justifications supplied by the employee in the confirmation modal.
  // Keyed as "expenseIndex-checkIndex" → free-text reason.
  const policyJustifications = req.body?.policyJustifications || {};

  const expenses = (folder.processedExpenses || [])
    .filter(e => e.status !== 'error')
    .filter(e => e.amount && e.amount > 0)   // skip zero-amount receipts — L3 rejects amount=0
    .filter(e => e.vendor)                   // skip receipts where OCR extracted no vendor
    .map(toL3ExpenseInput);

  // Count skipped receipts for the response
  const skippedCount = (folder.processedExpenses || [])
    .filter(e => e.status !== 'error' && (!e.amount || e.amount <= 0 || !e.vendor)).length;

  try {
    // Step 1 — push all expenses into Layer 3
    let expenseResp = null;
    if (expenses.length > 0) {
      expenseResp = await layer3.submitExpenses(
        folder.reportId,
        folder.employeeId,
        expenses
      );
    }

    // Step 2 — transition report to SUBMITTED
    const submitResp = await layer3.submitReport(folder.reportId);

    reportStore.update(folder.reportId, {
      status:               'SUBMITTED',
      submittedAt:          new Date().toISOString(),
      policyJustifications: policyJustifications,
    });

    // Normalise warnings — ensure they are always plain strings, never objects
    const rawWarnings = expenseResp?.warnings || [];
    const safeWarnings = rawWarnings.map(w => {
      if (typeof w === 'string') return { code: 'WARNING', message: w, severity: 'WARNING' };
      if (typeof w === 'object' && w !== null) {
        return {
          code:     w.code    || 'WARNING',
          message:  w.message || w.msg || JSON.stringify(w),
          severity: w.severity || 'WARNING',
          field:    w.field   || w.loc?.join('.') || undefined,
        };
      }
      return { code: 'WARNING', message: String(w), severity: 'WARNING' };
    });

    res.json({
      reportId:          folder.reportId,
      status:            submitResp.status || 'SUBMITTED',
      message:           skippedCount > 0
        ? `Report submitted. ${expenses.length} expense${expenses.length !== 1 ? 's' : ''} submitted; ${skippedCount} receipt${skippedCount !== 1 ? 's' : ''} skipped (OCR could not extract amount/vendor from image PDFs).`
        : (submitResp.message || 'Report submitted successfully'),
      warnings:          safeWarnings,
      validationSummary: expenseResp?.summary || null,
    });
  } catch (err) {
    const status = err.response?.status || 502;
    const rawBody = err.response?.data;

    // Parse Pydantic 422 validation errors into a clean human-readable message
    if (status === 422 && rawBody) {
      const detail = rawBody.detail || rawBody;
      // Pydantic v2 returns detail as array of {type, loc, msg, input, ctx}
      if (Array.isArray(detail)) {
        const messages = detail.map(e => {
          const loc = Array.isArray(e.loc) ? e.loc.join(' → ') : String(e.loc || '');
          const msg = e.msg || e.message || JSON.stringify(e);
          return loc ? `${loc}: ${msg}` : msg;
        });
        return res.status(422).json({
          error: 'Expense validation failed',
          detail: messages.join('; '),
          issues: messages,
        });
      }
      // L3 custom error shape {code, message}
      if (rawBody.code && rawBody.message) {
        return res.status(status).json({ error: rawBody.message });
      }
    }

    const errorMessage = rawBody?.error || rawBody?.detail || rawBody?.message
      || 'Failed to submit report to Layer 3';
    res.status(status).json({ error: typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage) });
  }
});

module.exports = router;
