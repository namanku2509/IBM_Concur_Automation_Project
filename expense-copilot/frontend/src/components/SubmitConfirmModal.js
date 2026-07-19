import React, { useState } from 'react';
import './SubmitConfirmModal.css';

// ── Policy rules (mirrors concur-stub seed data) ──────────────────────────────
// Keyed by policy name → expense type → rule → limit.
// "ALL" rules apply to every expense type.
const POLICY_RULES = {
  STANDARD: {
    HOTEL:  { NIGHTLY_LIMIT: 6000 },
    MEAL:   { MEAL_LIMIT: 1000 },
    FLIGHT: { MAX_TRAVEL_CLASS: 'ECONOMY' },
    ALL:    { ALLOWED_CURRENCIES: ['INR'] },
  },
  EXECUTIVE: {
    HOTEL:  { NIGHTLY_LIMIT: 12000 },
    MEAL:   { MEAL_LIMIT: 2500 },
    FLIGHT: { MAX_TRAVEL_CLASS: 'BUSINESS' },
    ALL:    { ALLOWED_CURRENCIES: ['INR', 'USD', 'GBP', 'EUR'] },
  },
};

const TRAVEL_CLASS_ORDER = { ECONOMY: 0, BUSINESS: 1, FIRST: 2 };

/**
 * Run policy checks for a single expense.
 * Returns an array of { rule, pass, reason } objects.
 */
function checkExpense(expense, policy) {
  const rules = POLICY_RULES[policy] || POLICY_RULES['STANDARD'];
  const typeRules  = rules[expense.expenseType] || {};
  const globalRules = rules['ALL'] || {};
  const checks = [];

  // ── Currency check ─────────────────────────────────────────────────────────
  const allowedCurrencies = globalRules.ALLOWED_CURRENCIES || ['INR'];
  const currency = expense.currency || 'INR';
  checks.push({
    rule: 'Allowed currency',
    pass: allowedCurrencies.includes(currency),
    reason: allowedCurrencies.includes(currency)
      ? `${currency} is accepted under this policy`
      : `${currency} is not allowed — accepted: ${allowedCurrencies.join(', ')}`,
  });

  // ── Payment type ───────────────────────────────────────────────────────────
  const isMatched = !!expense.matchedTxnId;
  checks.push({
    rule: 'Corporate card match',
    pass: isMatched,
    reason: isMatched
      ? `Matched to card transaction ${expense.matchedTxnId}`
      : 'No matching card transaction found — will be submitted as out-of-pocket',
  });

  // ── Type-specific limits ───────────────────────────────────────────────────
  if (expense.expenseType === 'HOTEL' && typeRules.NIGHTLY_LIMIT) {
    const rate = expense.hotelDetail?.nightly_rate
      ?? expense.hotelDetail?.nightlyRate
      ?? expense.amount;
    const limit = typeRules.NIGHTLY_LIMIT;
    const pass = rate <= limit;
    checks.push({
      rule: 'Hotel nightly rate limit',
      pass,
      reason: pass
        ? `₹${rate?.toLocaleString('en-IN')} / night is within the ₹${limit.toLocaleString('en-IN')} limit`
        : `₹${rate?.toLocaleString('en-IN')} / night exceeds the ₹${limit.toLocaleString('en-IN')} policy limit`,
    });
  }

  if (expense.expenseType === 'MEAL' && typeRules.MEAL_LIMIT) {
    const limit = typeRules.MEAL_LIMIT;
    const pass = expense.amount <= limit;
    checks.push({
      rule: 'Meal amount limit',
      pass,
      reason: pass
        ? `₹${expense.amount?.toLocaleString('en-IN')} is within the ₹${limit.toLocaleString('en-IN')} per-meal limit`
        : `₹${expense.amount?.toLocaleString('en-IN')} exceeds the ₹${limit.toLocaleString('en-IN')} per-meal policy limit`,
    });
  }

  if (expense.expenseType === 'FLIGHT' && typeRules.MAX_TRAVEL_CLASS) {
    const maxClass = typeRules.MAX_TRAVEL_CLASS;
    const actual = (
      expense.airfareDetail?.travel_class
      ?? expense.airfareDetail?.travelClass
      ?? 'ECONOMY'
    ).toUpperCase();
    const pass = (TRAVEL_CLASS_ORDER[actual] ?? 0) <= (TRAVEL_CLASS_ORDER[maxClass] ?? 0);
    checks.push({
      rule: 'Flight travel class',
      pass,
      reason: pass
        ? `${actual} class is within the ${maxClass} maximum allowed`
        : `${actual} class exceeds the ${maxClass} maximum allowed under this policy`,
    });
  }

  return checks;
}

// ── Formatters ────────────────────────────────────────────────────────────────
function fmtAmount(amount, currency = 'INR') {
  if (!amount && amount !== 0) return '—';
  return `${currency} ${Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const TYPE_LABELS = {
  HOTEL: 'Hotel', FLIGHT: 'Flight', TAXI: 'Taxi',
  MEAL: 'Meal', MEALS: 'Meal', REGISTRATION: 'Registration',
};

// ── Component ─────────────────────────────────────────────────────────────────
function SubmitConfirmModal({ meta, expenses, warnings, policy, onConfirm, onCancel, submitting }) {
  if (!meta) return null;

  // justifications keyed by "expenseIndex-checkIndex" for each failing check
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const [justifications, setJustifications] = useState({});

  function setJustification(key, value) {
    setJustifications(prev => ({ ...prev, [key]: value }));
  }

  // All valid expenses (exclude status=error rows — they were already filtered by BFF)
  const validExpenses   = expenses.filter(e => e.status !== 'error');
  const matchedExpenses = validExpenses.filter(e => e.matchedTxnId);
  const cashExpenses    = validExpenses.filter(e => !e.matchedTxnId && e.status !== 'duplicate');
  const matchedCount    = matchedExpenses.length;
  const totalAmount     = validExpenses.reduce((s, e) => s + (e.amount || 0), 0);
  const policyLabel     = { STANDARD: 'Standard', EXECUTIVE: 'Executive' }[policy] || policy;

  // Run policy checks for ALL valid expenses (card + cash), not just matched ones.
  const expenseChecks = validExpenses
    .filter(e => e.status !== 'duplicate')
    .map(e => ({
      expense: e,
      checks: checkExpense(e, policy),
    }));

  // Aggregate: how many checks pass vs fail across all expenses
  const allChecks    = expenseChecks.flatMap(ec => ec.checks);
  const passCount    = allChecks.filter(c => c.pass).length;
  const failCount    = allChecks.filter(c => !c.pass).length;

  // All failing checks that require a justification must have non-empty text
  const failingKeys  = expenseChecks.flatMap(({ checks }, ei) =>
    checks.map((c, ci) => (!c.pass ? `${ei}-${ci}` : null)).filter(Boolean)
  );
  const allJustified = failingKeys.every(k => (justifications[k] || '').trim().length > 0);
  const canConfirm   = failCount === 0 || allJustified;

  // Also include any server-side warnings (from Layer 3 / Layer 2)
  const serverWarnings = (warnings || []).filter(
    w => w.code !== 'RECEIPT_PROCESSING_FAILED' && w.code !== 'DUPLICATE_RECEIPT'
  );

  return (
    <div className="scm-backdrop" role="dialog" aria-modal="true" aria-labelledby="scm-title">
      <div className="scm-panel">

        {/* Header */}
        <div className="scm-header">
          <div>
            <p className="scm-eyebrow">SUBMISSION REVIEW</p>
            <h2 id="scm-title" className="scm-title">Confirm Expense Report</h2>
          </div>
          <button className="scm-close" onClick={onCancel} aria-label="Close">✕</button>
        </div>

        <div className="scm-body">

          {/* Report meta */}
          <div className="scm-meta-grid">
            <div className="scm-meta-item">
              <span className="scm-meta-label">Report</span>
              <span className="scm-meta-value">{meta.reportName || '—'}</span>
            </div>
            <div className="scm-meta-item">
              <span className="scm-meta-label">Employee</span>
              <span className="scm-meta-value">{meta.employeeId || '—'}</span>
            </div>
            <div className="scm-meta-item">
              <span className="scm-meta-label">Policy</span>
              <span className="scm-meta-value">{policyLabel}</span>
            </div>
            <div className="scm-meta-item">
              <span className="scm-meta-label">Total amount</span>
              <span className="scm-meta-value scm-total">{fmtAmount(totalAmount)}</span>
            </div>
            <div className="scm-meta-item">
              <span className="scm-meta-label">Expenses</span>
              <span className="scm-meta-value">{validExpenses.filter(e => e.status !== 'duplicate').length} item{validExpenses.filter(e => e.status !== 'duplicate').length !== 1 ? 's' : ''}</span>
            </div>
            <div className="scm-meta-item">
              <span className="scm-meta-label">Card matched</span>
              <span className="scm-meta-value">{matchedCount} matched · {cashExpenses.length} cash</span>
            </div>
          </div>

          {/* Policy summary bar */}
          <div className={`scm-policy-bar ${failCount === 0 ? 'scm-policy-bar--pass' : 'scm-policy-bar--warn'}`}>
            <span className="scm-policy-bar-icon">{failCount === 0 ? '✓' : '⚠'}</span>
            <span className="scm-policy-bar-text">
              {failCount === 0
                ? `All ${passCount} policy checks passed`
                : `${passCount} checks passed · ${failCount} check${failCount !== 1 ? 's' : ''} need attention`}
            </span>
          </div>

          {/* Expense rows with inline policy checks */}
          <div className="scm-section-label">Expenses &amp; Policy Checks</div>
          <div className="scm-expenses">
            {expenseChecks.map(({ expense: e, checks }, i) => {
              const hasFailure = checks.some(c => !c.pass);
              return (
                <div key={e.expenseId || i} className={`scm-expense-card ${hasFailure ? 'scm-expense-card--warn' : ''}`}>

                  {/* Expense summary row */}
                  <div className="scm-expense-summary">
                    <span className={`scm-exp-type scm-exp-type--${(e.expenseType || 'OTHER').toLowerCase()}`}>
                      {TYPE_LABELS[e.expenseType] || e.expenseType || '—'}
                    </span>
                    <span className="scm-exp-vendor">{e.vendor || '—'}</span>
                    <span className="scm-exp-amount">{fmtAmount(e.amount, e.currency)}</span>
                    <span className="scm-exp-date">{e.transactionDate || '—'}</span>
                    <span className={`scm-exp-match ${e.matchedTxnId ? 'scm-exp-match--yes' : 'scm-exp-match--no'}`}>
                      {e.matchedTxnId ? '● Card' : '○ Cash'}
                    </span>
                  </div>

                  {/* Policy checks for this expense */}
                  <div className="scm-checks">
                    {checks.map((c, j) => {
                      const jKey = `${i}-${j}`;
                      return (
                        <div key={j} className={`scm-check ${c.pass ? 'scm-check--pass' : 'scm-check--fail'}`}>
                          <span className="scm-check-icon">{c.pass ? '✓' : '✗'}</span>
                          <span className="scm-check-rule">{c.rule}</span>
                          <span className="scm-check-reason">{c.reason}</span>
                          {/* Justification input — only shown for failing checks */}
                          {!c.pass && (
                            <div className="scm-justify-wrap">
                              <label className="scm-justify-label" htmlFor={`justify-${jKey}`}>
                                Business justification for policy exception <span className="scm-justify-req">*</span>
                              </label>
                              <textarea
                                id={`justify-${jKey}`}
                                className={`scm-justify-input ${(justifications[jKey] || '').trim() ? '' : 'scm-justify-input--empty'}`}
                                rows={2}
                                placeholder="Enter reason for exceeding policy limit…"
                                value={justifications[jKey] || ''}
                                onChange={ev => setJustification(jKey, ev.target.value)}
                              />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                </div>
              );
            })}
          </div>

          {/* Server-side warnings from Layer 3 */}
          {serverWarnings.length > 0 && (
            <div className="scm-server-warns">
              <div className="scm-section-label">Additional Warnings</div>
              {serverWarnings.map((w, i) => (
                <div key={i} className={`scm-server-warn ${w.severity === 'ERROR' ? 'scm-server-warn--error' : ''}`}>
                  <span className="scm-server-warn-code">{(w.code || 'WARNING').replace(/_/g, ' ')}</span>
                  <span className="scm-server-warn-msg">{w.message}</span>
                </div>
              ))}
            </div>
          )}

        </div>

        {/* Footer */}
        {!canConfirm && (
          <div className="scm-justify-notice">
            ⚠ Please provide a business justification for each policy exception above before submitting.
          </div>
        )}
        <div className="scm-footer">
          <button className="scm-btn-cancel" onClick={onCancel} disabled={submitting}>
            Cancel
          </button>
          <button
            className="scm-btn-submit"
            onClick={() => onConfirm(justifications)}
            disabled={submitting || !canConfirm}
            title={!canConfirm ? 'Provide justifications for all policy exceptions to continue' : ''}
          >
            {submitting ? 'Submitting…' : 'Confirm & Submit →'}
          </button>
        </div>

      </div>
    </div>
  );
}

export default SubmitConfirmModal;
