const express = require('express');
const multer = require('multer');
const router = express.Router();

// Accept files in memory (no disk writes needed for mock)
const upload = multer({ storage: multer.memoryStorage() });

// ─────────────────────────────────────────────
// Simulated OCR + extraction results
// In the real system, Layer 2 would run OCR on each uploaded file.
// Here we return deterministic mock results so Layer 1 can be
// developed and tested without the real AI pipeline.
//
// The mock returns one processed expense per uploaded file,
// cycling through a realistic set of expense types.
// ─────────────────────────────────────────────

const MOCK_EXPENSES = [
  {
    expenseType: 'HOTEL',
    vendor: 'Marriott Bengaluru',
    amount: 18000,
    currency: 'INR',
    transactionDate: '2026-07-21',
    city: 'Bengaluru',
    paymentType: 'CORPORATE_CARD',
    matchedTxnId: 'TXN001',
    hotelDetails: {
      checkInDate: '2026-07-21',
      checkOutDate: '2026-07-23',
      numNights: 2,
      nightlyRate: 9000,
      taxAmount: 0
    },
    warnings: [
      {
        code: 'POLICY_HOTEL_LIMIT',
        message: 'Hotel nightly rate INR 9,000 exceeds India Domestic policy limit of INR 8,000',
        severity: 'WARNING'
      }
    ]
  },
  {
    expenseType: 'TAXI',
    vendor: 'Uber',
    amount: 450,
    currency: 'INR',
    transactionDate: '2026-07-21',
    city: 'Bengaluru',
    paymentType: 'CORPORATE_CARD',
    matchedTxnId: 'TXN002',
    taxiDetails: {
      fromLocation: 'Kempegowda International Airport',
      toLocation: 'Marriott Bengaluru'
    },
    warnings: []
  },
  {
    expenseType: 'FLIGHT',
    vendor: 'Air India',
    amount: 8500,
    currency: 'INR',
    transactionDate: '2026-07-20',
    city: 'Bengaluru',
    paymentType: 'CORPORATE_CARD',
    matchedTxnId: 'TXN003',
    airfareDetails: {
      origin: 'DEL',
      destination: 'BLR',
      airline: 'Air India',
      travelClass: 'ECONOMY'
    },
    warnings: []
  },
  {
    expenseType: 'MEAL',
    vendor: 'Swiggy',
    amount: 650,
    currency: 'INR',
    transactionDate: '2026-07-22',
    city: 'Bengaluru',
    paymentType: 'CORPORATE_CARD',
    matchedTxnId: 'TXN004',
    mealDetails: {
      mealType: 'DINNER',
      numAttendees: 1,
      businessJustification: 'Working dinner during client visit'
    },
    warnings: []
  }
];

// ─────────────────────────────────────────────
// POST /receipts/process
// Accepts: multipart/form-data with fields:
//   - reportId (string)
//   - employeeId (string)
//   - files[] (one or more receipt images)
//   - availableTransactions (JSON string, optional)
//
// Returns: matched expenses with warnings
// ─────────────────────────────────────────────
router.post('/receipts/process', upload.array('files'), (req, res) => {
  const { reportId, employeeId } = req.body;
  const files = req.files || [];

  if (!reportId || !employeeId) {
    return res.status(422).json({
      error: 'Missing required fields: reportId and employeeId'
    });
  }

  if (files.length === 0) {
    return res.status(422).json({
      error: 'No receipt files uploaded'
    });
  }

  // Validate all uploaded files are PDFs
  const nonPdf = files.filter(f => f.mimetype !== 'application/pdf');
  if (nonPdf.length > 0) {
    return res.status(422).json({
      error: `Only PDF files are accepted. Invalid files: ${nonPdf.map(f => f.originalname).join(', ')}`
    });
  }

  // Return one mock expense per uploaded file (cycling through MOCK_EXPENSES)
  const processedExpenses = files.map((file, index) => {
    const template = MOCK_EXPENSES[index % MOCK_EXPENSES.length];
    const expenseId = `EXP-${Date.now()}-${index + 1}`;
    return {
      expenseId,
      ...template,
      receiptFileName: file.originalname,
      receiptSize: file.size
    };
  });

  const matched = processedExpenses.filter(e => e.matchedTxnId).length;
  const unmatched = processedExpenses.length - matched;
  const allWarnings = processedExpenses.flatMap(e => e.warnings);

  res.status(200).json({
    reportId,
    employeeId,
    processed: processedExpenses.length,
    matched,
    unmatched,
    expenses: processedExpenses,
    processingWarnings: allWarnings,
    validationSummary: {
      errors: 0,
      warnings: allWarnings.length,
      info: 0
    }
  });
});

// Health check
router.get('/health', (req, res) => {
  res.json({ layer: 'Layer 2 — AI Middleware Mock', status: 'ok' });
});

module.exports = router;
