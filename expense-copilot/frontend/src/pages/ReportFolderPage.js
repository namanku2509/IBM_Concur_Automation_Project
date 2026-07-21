import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import {
  Tile,
  Tag,
  Button,
  InlineNotification,
} from '@carbon/react';

import AvailableExpensesTable from '../components/AvailableExpensesTable';
import ReceiptUploadArea from '../components/ReceiptUploadArea';
import ProcessedExpensesTable from '../components/ProcessedExpensesTable';
import WarningsList from '../components/WarningsList';
import ChatPanel from '../components/ChatPanel';
import SubmitConfirmModal from '../components/SubmitConfirmModal';

import {
  getTransactions,
  processReceipts,
  submitReport,
  removeExpense,
} from '../services/reportService';

import './ReportFolderPage.css';

// ── Label maps ────────────────────────────────────────────────────────────────
const POLICY_LABELS = {
  STANDARD:  'Standard',
  EXECUTIVE: 'Executive',
  TRAVEL_AND_EXPENSE_AP_NON_VAT: 'Travel & Expense (AP Non-VAT)',
};

const CATEGORY_LABELS = {
  TRAVEL:                            'Travel',
  CONFERENCE_TRADESHOW_CUSTOMER:     'Conference / Tradeshow (Customer)',
  CONFERENCE_TRADESHOW_NON_CUSTOMER: 'Conference / Tradeshow (Internal)',
  CORPORATE_EVENT_RECOGNITION:       'Corporate Event / Recognition',
  CUSTOMER_CLIENT_RELATED_TRAVEL:    'Customer / Client Related Travel',
  EDUCATION_SEMINAR:                 'Education / Seminar',
  NON_TRAVEL_EXPENSES:               'Non-Travel Expenses',
};

// ── Pipeline steps definition ────────────────────────────────────────────────
const PIPELINE_STEPS = [
  { id: 'CREATE',       label: 'Report Created',              desc: 'Shell report registered in the system' },
  { id: 'TXN_FETCH',    label: 'Card Transactions Loaded',    desc: 'Corporate card feed fetched' },
  { id: 'OCR',          label: 'OCR Processing',              desc: 'Docling extracts text from PDF receipts' },
  { id: 'AI_EXTRACT',   label: 'AI Field Extraction',         desc: 'Ollama LLM extracts vendor, amount, date' },
  { id: 'MATCHING',     label: 'Transaction Matching',        desc: 'Fuzzy match receipts to card transactions' },
  { id: 'SUBMIT',       label: 'Submitted',                   desc: 'Expense report posted and locked' },
];

// step status: 'idle' | 'active' | 'done' | 'error'

function PipelineTracker({ stepStatuses, matchStats }) {
  return (
    <div className="pipeline-tracker">
      <p className="pipeline-title">Pipeline Status</p>
      <div className="pipeline-steps">
        {PIPELINE_STEPS.map((step, i) => {
          const status = stepStatuses[step.id] || 'idle';
          return (
            <div key={step.id} className={`pipeline-step pipeline-step--${status}`}>
              <div className="pipeline-step-indicator">
                <div className="pipeline-step-dot">
                  {status === 'done'   && '✓'}
                  {status === 'active' && <span className="pipeline-spinner">⟳</span>}
                  {status === 'error'  && '✕'}
                  {status === 'idle'   && (i + 1)}
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div className={`pipeline-step-line pipeline-step-line--${status === 'done' ? 'done' : 'idle'}`} />
                )}
              </div>
              <div className="pipeline-step-body">
                <span className="pipeline-step-label">{step.label}</span>
                <span className="pipeline-step-desc">{step.desc}</span>
                {step.id === 'MATCHING' && status === 'done' && matchStats && (
                  <span className="pipeline-step-stat">
                    {matchStats.matched}/{matchStats.total} matched
                    {matchStats.matched > 0 && ` (${Math.round(matchStats.matched/matchStats.total*100)}%)`}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
function ReportFolderPage() {
  const { reportId } = useParams();
  const location     = useLocation();
  const navigate     = useNavigate();
  // When opened from the unified dashboard (new tab), location.state is null.
  // Fall back to URL query params which the dashboard passes via URLSearchParams.
  const metaFromState = location.state || {};
  const metaFromQuery = Object.fromEntries(new URLSearchParams(location.search));
  const meta = Object.keys(metaFromState).length > 0 ? metaFromState : metaFromQuery;

  // ── Receipt preview URLs — keyed by filename, built from File objects at upload time ──
  const receiptUrlsRef = React.useRef({});

  // ── Core state ────────────────────────────────────────────────────────────
  const [folderStatus,       setFolderStatus]       = useState('DRAFT');
  const [transactions,       setTransactions]       = useState([]);
  const [txnLoading,         setTxnLoading]         = useState(true);
  const [txnError,           setTxnError]           = useState(null);
  const [processedExpenses,  setProcessedExpenses]  = useState([]);
  const [removedExpenseIds,  setRemovedExpenseIds]  = useState([]); // eslint-disable-line no-unused-vars
  const [warnings,           setWarnings]           = useState([]);
  const [processing,         setProcessing]         = useState(false);
  const [processingCash,     setProcessingCash]     = useState(false);
  const [submitting,         setSubmitting]         = useState(false);
  const [submitError,        setSubmitError]        = useState(null);
  const [confirmation,       setConfirmation]       = useState(null);
  const [chatMessages,       setChatMessages]       = useState([]);
  const [showModal,          setShowModal]          = useState(false);

  // ── Pipeline tracker state ─────────────────────────────────────────────────
  const [stepStatuses, setStepStatuses] = useState({
    CREATE:     'done',   // already done when we land here
    TXN_FETCH:  'active',
    OCR:        'idle',
    AI_EXTRACT: 'idle',
    MATCHING:   'idle',
    SUBMIT:     'idle',
  });
  const [matchStats, setMatchStats] = useState(null);

  function setStep(id, status) {
    setStepStatuses(prev => ({ ...prev, [id]: status }));
  }

  // ── Chat helper ───────────────────────────────────────────────────────────
  const addAgentMessage = useCallback(message => {
    const entry = typeof message === 'string'
      ? { from: 'agent', text: message, ts: new Date().toLocaleTimeString() }
      : message;
    setChatMessages(prev => [...prev, entry]);
  }, []);

  // ── BroadcastChannel helper — updates dashboard pipeline panel live ────────
  const broadcastPipelineStep = useCallback((step, done, hint) => {
    try {
      if (typeof BroadcastChannel !== 'undefined') {
        const bc = new BroadcastChannel('roam-expense');
        bc.postMessage({ type: 'pipeline-step', step, done, hint });
        bc.close();
      }
    } catch (_) {}
  }, []);

  // ── Step 2: Load transactions on mount ───────────────────────────────────
  useEffect(() => {
    const empId    = meta.employeeId || 'EMP001';
    const policy   = POLICY_LABELS[meta.policy] || meta.policy || 'STANDARD';
    addAgentMessage(
      `Report folder created ✅\nEmployee: ${empId} | Policy: ${policy}\nFetching corporate card transactions…`
    );

    async function load() {
      setStep('TXN_FETCH', 'active');
      broadcastPipelineStep('txn', ['create'], 'Fetching corporate card transactions…');
      try {
        const data = await getTransactions(reportId);
        setTransactions(data.transactions || []);
        setFolderStatus('EXPENSES_LOADED');
        setStep('TXN_FETCH', 'done');
        broadcastPipelineStep('ocr', ['create', 'txn'],
          `✓ ${data.totalCount} card transaction${data.totalCount !== 1 ? 's' : ''} loaded. Upload receipts to continue.`);
        addAgentMessage(
          `Found ${data.totalCount} transaction${data.totalCount !== 1 ? 's' : ''} on your corporate card.\nUpload your PDF receipts to begin AI processing.`
        );
      } catch (err) {
        setStep('TXN_FETCH', 'error');
        const msg = err.response?.data?.error
          || err.response?.data?.detail
          || 'Failed to load transactions.';
        setTxnError(msg);
        addAgentMessage(`❌ Could not load transactions: ${msg}`);
      } finally {
        setTxnLoading(false);
      }
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  // ── Step 3-5: Receipt upload → OCR → AI → Match ──────────────────────────
  async function handleUpload(files) {
    Array.from(files).forEach(file => {
      if (!receiptUrlsRef.current[file.name]) {
        receiptUrlsRef.current[file.name] = URL.createObjectURL(file);
      }
    });
    setProcessing(true);
    setFolderStatus('PROCESSING');
    setSubmitError(null);

    // Animate OCR step
    setStep('OCR', 'active');
    const estSecs = files.length * 45;
    const estMins = Math.ceil(estSecs / 60);
    broadcastPipelineStep('ocr', ['create', 'txn'],
      `⟳ OCR processing ${files.length} receipt${files.length !== 1 ? 's' : ''}… (~${estMins} min)`);
    addAgentMessage(
      `Sending ${files.length} receipt${files.length !== 1 ? 's' : ''} for OCR processing via Docling…\n` +
      `⏱ Estimated time: ~${estMins} min${estMins !== 1 ? 's' : ''} (${files.length} × ~45s per receipt on this VM)`
    );

    try {
      // Simulate stage transitions during the API call
      const perReceiptMs = 45000;
      const ocrTimer = setTimeout(() => {
        setStep('OCR', 'done');
        setStep('AI_EXTRACT', 'active');
        broadcastPipelineStep('ai', ['create', 'txn', 'ocr'], '⟳ AI extracting vendor, amount, date…');
        addAgentMessage('OCR complete ✅ — Ollama LLM now extracting fields (vendor, amount, date, city)…');
      }, Math.max(files.length * perReceiptMs * 0.6, 5000));

      const aiTimer = setTimeout(() => {
        setStep('AI_EXTRACT', 'done');
        setStep('MATCHING', 'active');
        broadcastPipelineStep('match', ['create', 'txn', 'ocr', 'ai'], '⟳ Matching receipts to card transactions…');
        addAgentMessage('AI extraction complete ✅ — Matching receipts to corporate card transactions…');
      }, Math.max(files.length * perReceiptMs * 0.85, 10000));

      const data = await processReceipts(reportId, files, 'card');

      clearTimeout(ocrTimer);
      clearTimeout(aiTimer);

      const expenses  = data.expenses || [];
      const allWarns  = data.warnings  || [];
      const matched   = data.matched   ?? expenses.filter(e => e.matchedTxnId).length;
      const total     = data.processed ?? expenses.length;

      const successExpenses = expenses
        .filter(e => e.status !== 'error' && e.status !== 'duplicate')
        .map(e => ({ ...e, fromCashZone: false }));
      const wrongBoxErrors  = expenses.filter(e => e.status === 'error' && (
        e.errorMessage?.includes('Cash payment') || e.errorMessage?.includes('Out-of-Pocket')
      ));
      const ocrFailures     = expenses.filter(e => e.status === 'error' && !wrongBoxErrors.includes(e));
      // Append new card results after existing expenses, avoiding duplicate file hashes.
      setProcessedExpenses(prev => {
        const existingHashes = new Set(prev.map(e => e.fileHash).filter(Boolean));
        const duplicateExpenses = expenses
          .filter(e => e.status === 'duplicate')
          .map((e, index) => ({
            ...e,
            fromCashZone: false,
            duplicateEntryId: `${e.fileHash || e.filename || 'duplicate'}-${index}-${Date.now()}`,
          }));
        const uniqueSuccessExpenses = successExpenses.filter(e => !e.fileHash || !existingHashes.has(e.fileHash));
        return [...prev, ...uniqueSuccessExpenses, ...duplicateExpenses];
      });
      setWarnings(prev => [...prev, ...allWarns]);
      // Only update match stats when there are actual card-zone successes to show
      if (successExpenses.length > 0) {
        setMatchStats(prev => ({
          matched: (prev?.matched || 0) + matched,
          total: (prev?.total || 0) + successExpenses.length,
        }));
        setFolderStatus('REVIEW');
      } else {
        // Duplicate-only upload: we set folderStatus to 'PROCESSING' at the start
        // of handleUpload, so prev is 'PROCESSING' here — not 'REVIEW'.
        // Restore to 'REVIEW' if there are already successfully matched expenses,
        // otherwise fall back to 'EXPENSES_LOADED'.
        setFolderStatus(() => {
          const hasExisting = processedExpenses.some(
            e => e.status !== 'duplicate' && !e.duplicateEntryId && e.status !== 'error'
          );
          return hasExisting ? 'REVIEW' : 'EXPENSES_LOADED';
        });
      }

      const allFailed = expenses.length > 0 && successExpenses.length === 0;
      setStep('OCR',        allFailed ? 'error' : 'done');
      setStep('AI_EXTRACT', allFailed ? 'idle'  : 'done');
      setStep('MATCHING',   allFailed ? 'idle'  : 'done');
      if (!allFailed) {
        broadcastPipelineStep('submit', ['create','txn','ocr','ai','match'],
          `✓ ${successExpenses.length} expense${successExpenses.length !== 1 ? 's' : ''} processed — ${matched} card matched. Ready to submit.`);
      }

      const policyWarnCount = allWarns.filter(w => w.code !== 'RECEIPT_PROCESSING_FAILED').length;
      const lines = [
        `Processing complete${allFailed ? ' with errors' : ' ✅'}`,
        `• ${total} receipt${total !== 1 ? 's' : ''} submitted`,
      ];
      if (wrongBoxErrors.length > 0)
        lines.push(`• ❌ ${wrongBoxErrors.length} receipt${wrongBoxErrors.length !== 1 ? 's' : ''} rejected — contains a Cash payment, use the Cash Receipts drop box`);
      if (ocrFailures.length > 0)
        lines.push(`• ❌ ${ocrFailures.length} receipt${ocrFailures.length !== 1 ? 's' : ''} could not be read by OCR — PDF may be a scanned image`);
      if (successExpenses.length > 0)
        lines.push(`• ${matched} of ${successExpenses.length} matched to corporate card`);
      if (policyWarnCount > 0)
        lines.push(`• ⚠️ ${policyWarnCount} policy warning${policyWarnCount !== 1 ? 's' : ''} — review before submitting`);
      else if (successExpenses.length > 0)
        lines.push('• No policy violations found');
      addAgentMessage(lines.join('\n'));
    } catch (err) {
      // 409 = all files already added to this report
      if (err.response?.status === 409) {
        addAgentMessage(`ℹ️ ${err.response.data?.error || 'These receipts have already been added to this report.'}`);
        return;
      }
      setStep('OCR',        'error');
      setStep('AI_EXTRACT', 'idle');
      setStep('MATCHING',   'idle');
      setFolderStatus('EXPENSES_LOADED');
      const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout');
      const msg = isTimeout
        ? `Request timed out — ${files.length} receipts took too long. Try uploading fewer receipts at a time (2–3 max).`
        : (err.response?.data?.error || err.response?.data?.detail || 'Receipt processing failed.');
      addAgentMessage(`❌ Processing failed: ${msg}\nTip: Upload 2–3 receipts at a time for best results.`);
    } finally {
      setProcessing(false);
    }
  }

  // ── Cash receipts: same pipeline, results appended, no card match expected ──
  async function handleCashUpload(files) {
    Array.from(files).forEach(file => {
      if (!receiptUrlsRef.current[file.name]) {
        receiptUrlsRef.current[file.name] = URL.createObjectURL(file);
      }
    });
    setProcessingCash(true);
    setSubmitError(null);

    const count = files.length;
    addAgentMessage(
      `Sending ${count} cash receipt${count !== 1 ? 's' : ''} for processing…\n` +
      `These will be added as out-of-pocket expenses (no card match required).`
    );

    try {
      const data = await processReceipts(reportId, files, 'cash');

      const expenses = data.expenses || [];
      const allWarns = data.warnings || [];

      const successExpenses = expenses
        .filter(e => e.status !== 'error' && e.status !== 'duplicate')
        .map(e => ({ ...e, fromCashZone: true }));

      // Append to existing processed expenses — deduplicate by fileHash.
      // Keep the state updater pure (no side-effects inside it).
      setProcessedExpenses(prev => {
        const existingHashes = new Set(prev.map(e => e.fileHash).filter(Boolean));
        const newExpenses = successExpenses.filter(e => !e.fileHash || !existingHashes.has(e.fileHash));
        return [...prev, ...newExpenses];
      });
      // Set folder status separately — never call setState inside another setState updater
      if (successExpenses.length > 0) setFolderStatus('REVIEW');
      setWarnings(prev => [...prev, ...allWarns]);

      const wrongBoxErrors = expenses.filter(e => e.status === 'error' && (
        e.errorMessage?.includes('Corporate Card') || e.errorMessage?.includes('Cash payment')
      ));
      const ocrFailures2 = expenses.filter(e => e.status === 'error' && !wrongBoxErrors.includes(e));

      const lines = [
        `Cash receipt processing complete${(ocrFailures2.length + wrongBoxErrors.length) > 0 ? ' with errors' : ' ✅'}`,
        `• ${successExpenses.length} expense${successExpenses.length !== 1 ? 's' : ''} added as out-of-pocket`,
      ];
      if (wrongBoxErrors.length > 0)
        lines.push(`• ❌ ${wrongBoxErrors.length} receipt${wrongBoxErrors.length !== 1 ? 's' : ''} rejected — contains a Corporate Card payment, use the Card Receipts drop box`);
      if (ocrFailures2.length > 0)
        lines.push(`• ❌ ${ocrFailures2.length} receipt${ocrFailures2.length !== 1 ? 's' : ''} could not be read by OCR — PDF may be a scanned image`);
      if (successExpenses.length === 0 && wrongBoxErrors.length === 0 && ocrFailures2.length === 0)
        lines.push('• All receipts extracted successfully');
      addAgentMessage(lines.join('\n'));
    } catch (err) {
      // 409 = all files already added to this report
      if (err.response?.status === 409) {
        addAgentMessage(`ℹ️ ${err.response.data?.error || 'These receipts have already been added to this report.'}`);
        return;
      }
      const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout');
      const msg = isTimeout
        ? `Request timed out. Try uploading fewer receipts at a time.`
        : (err.response?.data?.error || err.response?.data?.detail || 'Receipt processing failed.');
      addAgentMessage(`❌ Cash receipt processing failed: ${msg}`);
    } finally {
      setProcessingCash(false);
    }
  }

  // ── Step 6: Submit ────────────────────────────────────────────────────────
  // "Submit" button opens the confirmation modal.
  // The actual API call fires only when the employee clicks Confirm in the modal.
  function handleSubmitClick() {
    setShowModal(true);
  }

  async function handleSubmit(justifications = {}) {
    setShowModal(false);
    setSubmitting(true);
    setSubmitError(null);
    setStep('SUBMIT', 'active');
    addAgentMessage('Submitting expense report…');

    try {
      const data = await submitReport(reportId, justifications);
      setConfirmation(data);
      setFolderStatus('SUBMITTED');
      setStep('SUBMIT', 'done');
      addAgentMessage(
        `Report submitted successfully 🎉\n` +
        `Status: ${data.status}\n` +
        `${data.message || ''}`
      );
      // Notify the travel dashboard (same browser, any tab) so it refreshes
      // and moves the claimed txn IDs from Available → Claimed.
      try {
        if (typeof BroadcastChannel !== 'undefined') {
          const bc = new BroadcastChannel('roam-expense');
          // Include selectedTxnIds so the dashboard can immediately move those
          // rows from "Available for claim" to "Claimed transactions".
          const selectedTxnIds = transactions.map(t => t.transactionId).filter(Boolean);
          bc.postMessage({ type: 'report-submitted', reportId, selectedTxnIds });
          bc.close();
        }
      } catch (_) { /* BroadcastChannel not supported — silently ignore */ }
    } catch (err) {
      setStep('SUBMIT', 'error');
      const msg = err.response?.data?.error
        || err.response?.data?.detail
        || 'Submission failed.';
      setSubmitError(msg);
      addAgentMessage(`❌ Submission failed: ${msg}\nPlease try again.`);
    } finally {
      setSubmitting(false);
    }
  }

  // Only policy-level errors (not OCR failures) block submission.
  const hasPolicyErrors = warnings.some(
    w => w.severity === 'ERROR'
      && w.code !== 'RECEIPT_PROCESSING_FAILED'
      && w.code !== 'DUPLICATE_RECEIPT'
  );

  // Submit guard: every selected card transaction must have a receipt matched to it.
  // We check from the transactions side (not the expenses side) so:
  //   - Extra receipts that didn't match any selected txn don't enable submit
  //   - The count is based on what the user was required to upload, not what they did
  const matchedTxnIds = new Set(
    processedExpenses
      .filter(e => !e.fromCashZone && e.status !== 'duplicate' && !e.duplicateEntryId)
      .map(e => e.matchedTxnId)
      .filter(Boolean)
  );
  // transactions[] contains exactly the selected txns (filtered by BFF selectedTxnIds)
  const unmatchedTxns = transactions.filter(
    t => t.status === 'AVAILABLE' && !matchedTxnIds.has(t.transactionId)
  );
  const allTxnsMatched = transactions.length > 0 && unmatchedTxns.length === 0;

  const canSubmit = folderStatus === 'REVIEW' && !hasPolicyErrors && !submitting && allTxnsMatched;

  function handleRemoveExpense(expenseId) {
    // Remove from local UI state immediately (optimistic)
    setProcessedExpenses(prev => prev.filter(expense => (expense.duplicateEntryId || expense.expenseId) !== expenseId));
    setWarnings(prev => prev.filter(w => w.code !== 'DUPLICATE_RECEIPT'));
    setRemovedExpenseIds(prev => [...prev, expenseId]);

    // Tell the BFF to free the file hash so re-uploading the same receipt works.
    // Fire-and-forget — a failure here doesn't affect the UI (the row is already gone).
    removeExpense(reportId, expenseId).catch(() => {});
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="report-folder-page">

      {/* ── Main content ── */}
      <div className="report-folder-main">

        {/* Report header */}
        <Tile className="report-header-tile">
          <div className="report-header-top">
            <div>
              <h1 className="report-header-name">{meta.reportName || reportId}</h1>
              <p className="report-header-purpose">{meta.businessPurpose}</p>
            </div>
            <div className="report-header-meta">
              {meta.employeeId && (
                <Tag type="cyan" size="sm">{meta.employeeId}</Tag>
              )}
              <Tag type="blue" size="sm">{POLICY_LABELS[meta.policy] || meta.policy}</Tag>
              <Tag type="teal" size="sm">{CATEGORY_LABELS[meta.reportCategory] || meta.reportCategory}</Tag>
              <Tag
                type={
                  folderStatus === 'SUBMITTED'      ? 'green'
                  : folderStatus === 'REVIEW'       ? 'purple'
                  : folderStatus === 'PROCESSING'   ? 'blue'
                  : 'gray'
                }
                size="sm"
              >
                {folderStatus}
              </Tag>
            </div>
          </div>
          <p style={{ fontSize: '0.75rem', color: '#6f6f6f', margin: 0 }}>
            Report ID: <strong>{reportId}</strong>
          </p>
        </Tile>

        {/* Submission confirmation */}
        {confirmation && (
          <Tile className="confirmation-tile">
            <p className="confirmation-title">✅ Report Submitted Successfully</p>
            <p className="confirmation-id">
              {confirmation.message || `Status: ${confirmation.status}`}
            </p>
          </Tile>
        )}

        {/* Submit error */}
        {submitError && (
          <InlineNotification
            kind="error"
            title="Submission failed"
            subtitle={submitError}
            hideCloseButton
            style={{ marginBottom: '1rem' }}
          />
        )}

        {/* Available card transactions */}
        <div className="available-expenses-section">
          <p className="section-heading">
            Corporate Card Transactions
            {transactions.length > 0 && (
              <span className="section-count"> ({transactions.length})</span>
            )}
          </p>
          <AvailableExpensesTable
            transactions={transactions}
            loading={txnLoading}
            error={txnError}
          />
        </div>

        {/* Corporate card receipt upload */}
        {folderStatus !== 'SUBMITTED' && (
          <div className="receipt-upload-section">
            <p className="section-heading">
              Upload Corporate Card Receipts
              <span className="section-count"> — matched to card transactions automatically</span>
            </p>
            <ReceiptUploadArea
              onUpload={handleUpload}
              processing={processing}
              disabled={txnLoading || folderStatus === 'SUBMITTED'}
            />
          </div>
        )}

        {/* Cash / out-of-pocket receipt upload */}
        {folderStatus !== 'SUBMITTED' && (
          <div className="receipt-upload-section">
            <p className="section-heading">
              Upload Cash / Out-of-Pocket Receipts
              <span className="section-count"> — added as personal expenses, no card match needed</span>
            </p>
            <ReceiptUploadArea
              onUpload={handleCashUpload}
              processing={processingCash}
              disabled={txnLoading || folderStatus === 'SUBMITTED'}
              variant="cash"
            />
          </div>
        )}

        {/* Processed expenses table */}
        {processedExpenses.length > 0 && (
          <div className="processed-expenses-section">
            <p className="section-heading">
              Processed Expenses
              <span className="section-count">
                &nbsp;({processedExpenses.filter(e => e.matchedTxnId).length} card
                {' · '}
                {processedExpenses.filter(e => e.fromCashZone).length} cash
                {' of '}
                {processedExpenses.length} total)
              </span>
            </p>
            <ProcessedExpensesTable expenses={processedExpenses} onRemove={handleRemoveExpense} receiptUrls={receiptUrlsRef.current} />
          </div>
        )}

        {/* Policy warnings and OCR errors */}
        {warnings.length > 0 && (
          <div className="warnings-section">
            <p className="section-heading">
              {warnings.some(w => w.code === 'RECEIPT_PROCESSING_FAILED') && warnings.every(w => w.code === 'RECEIPT_PROCESSING_FAILED')
                ? `Receipt Errors (${warnings.length})`
                : `Warnings (${warnings.length})`}
            </p>
            <WarningsList warnings={warnings} />
          </div>
        )}

        {/* Submit bar */}
        {folderStatus !== 'SUBMITTED' && processedExpenses.length > 0 && (
          <div className="submit-bar">
            <p className="submit-bar-info">
              {hasPolicyErrors
                ? '⛔ Fix the policy errors above before submitting.'
                : !allTxnsMatched
                ? `⛔ ${unmatchedTxns.length} selected transaction${unmatchedTxns.length !== 1 ? 's' : ''} still need${unmatchedTxns.length === 1 ? 's' : ''} a matched receipt — upload receipts for them before submitting.`
                : warnings.filter(w => w.code !== 'RECEIPT_PROCESSING_FAILED').length > 0
                ? `⚠️ ${warnings.filter(w => w.code !== 'RECEIPT_PROCESSING_FAILED').length} policy warning${warnings.filter(w => w.code !== 'RECEIPT_PROCESSING_FAILED').length !== 1 ? 's' : ''} — you can still submit.`
                : '✅ All card transactions matched. Ready to submit.'}
            </p>
            <Button kind="secondary" onClick={() => navigate('/')} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmitClick} disabled={!canSubmit}>
              {submitting ? 'Submitting…' : 'Submit Expense Report'}
            </Button>
          </div>
        )}

      </div>

      {/* ── Right sidebar: pipeline status + WXO ── */}
      <aside className="status-sidebar">

        {/* Pipeline tracker */}
        <div className="ss-pipeline">
          <p className="ss-section-title">Processing Pipeline</p>
          <div className="ss-steps">
            {PIPELINE_STEPS.map((step, i) => {
              const status = stepStatuses[step.id] || 'idle';
              return (
                <div key={step.id} className={`ss-step ss-step--${status}`}>
                  <div className="ss-dot-col">
                    <div className="ss-dot">
                      {status === 'done'   && '✓'}
                      {status === 'active' && <span className="pipeline-spinner">⟳</span>}
                      {status === 'error'  && '✕'}
                      {status === 'idle'   && (i + 1)}
                    </div>
                    {i < PIPELINE_STEPS.length - 1 && (
                      <div className={`ss-connector ${status === 'done' ? 'ss-connector--done' : ''}`} />
                    )}
                  </div>
                  <div className="ss-step-body">
                    <span className="ss-step-label">{step.label}</span>
                    <span className="ss-step-desc">{step.desc}</span>
                    {step.id === 'MATCHING' && status === 'done' && matchStats && (
                      <span className="ss-step-stat">
                        {matchStats.matched}/{matchStats.total} matched
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Activity log */}
        <div className="ss-log">
          <p className="ss-section-title">Activity log</p>
          <div className="ss-log-entries">
            {chatMessages.length === 0 && (
              <p className="ss-log-empty">Steps will appear here as the pipeline runs.</p>
            )}
            {[...chatMessages].reverse().map((m, i) => (
              <div key={i} className="ss-log-entry">
                <span className="ss-log-ts">{m.ts}</span>
                <span className="ss-log-text">{m.text || m.message || String(m)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* WXO widget — only renders when configured */}
        <div className="ss-wxo">
          <ChatPanel />
        </div>

      </aside>

      {/* ── Submit confirmation modal ── */}
      {showModal && (
        <SubmitConfirmModal
          meta={meta}
          expenses={processedExpenses}
          warnings={warnings}
          policy={meta.policy || 'STANDARD'}
          onConfirm={handleSubmit}
          onCancel={() => setShowModal(false)}
          submitting={submitting}
        />
      )}

    </div>
  );
}

export default ReportFolderPage;
