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

import {
  getTransactions,
  processReceipts,
  submitReport,
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
  { id: 'CREATE',       label: 'Report Created',              desc: 'Shell report registered in SAP Concur' },
  { id: 'TXN_FETCH',    label: 'Card Transactions Loaded',    desc: 'Corporate card feed fetched from Concur' },
  { id: 'OCR',          label: 'OCR Processing',              desc: 'Docling extracts text from PDF receipts' },
  { id: 'AI_EXTRACT',   label: 'AI Field Extraction',         desc: 'Ollama LLM extracts vendor, amount, date' },
  { id: 'MATCHING',     label: 'Transaction Matching',        desc: 'Fuzzy match receipts to card transactions' },
  { id: 'SUBMIT',       label: 'Submitted to Concur',         desc: 'Expense report posted and locked' },
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
  const meta         = location.state || {};

  // ── Core state ────────────────────────────────────────────────────────────
  const [folderStatus,       setFolderStatus]       = useState('DRAFT');
  const [transactions,       setTransactions]       = useState([]);
  const [txnLoading,         setTxnLoading]         = useState(true);
  const [txnError,           setTxnError]           = useState(null);
  const [processedExpenses,  setProcessedExpenses]  = useState([]);
  const [warnings,           setWarnings]           = useState([]);
  const [processing,         setProcessing]         = useState(false);
  const [submitting,         setSubmitting]         = useState(false);
  const [submitError,        setSubmitError]        = useState(null);
  const [confirmation,       setConfirmation]       = useState(null);
  const [chatMessages,       setChatMessages]       = useState([]);

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
  const addAgentMessage = useCallback(text => {
    setChatMessages(prev => [
      ...prev,
      { from: 'agent', text, ts: new Date().toLocaleTimeString() }
    ]);
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
      try {
        const data = await getTransactions(reportId);
        setTransactions(data.transactions || []);
        setFolderStatus('EXPENSES_LOADED');
        setStep('TXN_FETCH', 'done');
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
    setProcessing(true);
    setFolderStatus('PROCESSING');
    setSubmitError(null);

    // Animate OCR step
    setStep('OCR', 'active');
    addAgentMessage(`Sending ${files.length} receipt${files.length !== 1 ? 's' : ''} for OCR processing via Docling…`);

    try {
      // Simulate stage transitions during the API call
      // (The actual stages happen inside Layer 2 — we show approximate progress)
      const ocrTimer = setTimeout(() => {
        setStep('OCR', 'done');
        setStep('AI_EXTRACT', 'active');
        addAgentMessage('OCR complete ✅ — Ollama LLM now extracting fields (vendor, amount, date, city)…');
      }, 3000);

      const aiTimer = setTimeout(() => {
        setStep('AI_EXTRACT', 'done');
        setStep('MATCHING', 'active');
        addAgentMessage('AI extraction complete ✅ — Matching receipts to corporate card transactions…');
      }, 8000);

      const data = await processReceipts(reportId, files);

      clearTimeout(ocrTimer);
      clearTimeout(aiTimer);

      const expenses  = data.expenses || [];
      const allWarns  = data.warnings  || [];
      const matched   = data.matched   ?? expenses.filter(e => e.matchedTxnId).length;
      const total     = data.processed ?? expenses.length;

      setProcessedExpenses(expenses);
      setWarnings(allWarns);
      setMatchStats({ matched, total });
      setFolderStatus('REVIEW');

      // Mark all processing steps done
      setStep('OCR',        'done');
      setStep('AI_EXTRACT', 'done');
      setStep('MATCHING',   'done');

      const warnCount = allWarns.length;
      addAgentMessage(
        `Processing complete ✅\n` +
        `• ${total} receipt${total !== 1 ? 's' : ''} processed\n` +
        `• ${matched} of ${total} matched to corporate card\n` +
        (warnCount > 0
          ? `• ⚠️ ${warnCount} policy warning${warnCount !== 1 ? 's' : ''} — review before submitting`
          : `• No policy violations found`)
      );
    } catch (err) {
      setStep('OCR',        'error');
      setStep('AI_EXTRACT', 'idle');
      setStep('MATCHING',   'idle');
      setFolderStatus('EXPENSES_LOADED');
      const msg = err.response?.data?.error
        || err.response?.data?.detail
        || 'Receipt processing failed.';
      addAgentMessage(`❌ Processing failed: ${msg}\nPlease try uploading again.`);
    } finally {
      setProcessing(false);
    }
  }

  // ── Step 6: Submit ────────────────────────────────────────────────────────
  async function handleSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    setStep('SUBMIT', 'active');
    addAgentMessage('Submitting expense report to SAP Concur stub…');

    try {
      const data = await submitReport(reportId);
      setConfirmation(data);
      setFolderStatus('SUBMITTED');
      setStep('SUBMIT', 'done');
      addAgentMessage(
        `Report submitted successfully 🎉\n` +
        `Status: ${data.status}\n` +
        `${data.message || ''}`
      );
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

  const hasErrors = warnings.some(w => w.severity === 'ERROR');
  const canSubmit = folderStatus === 'REVIEW' && !hasErrors && !submitting;

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

        {/* Pipeline tracker */}
        <PipelineTracker stepStatuses={stepStatuses} matchStats={matchStats} />

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

        {/* Receipt upload */}
        {folderStatus !== 'SUBMITTED' && (
          <div className="receipt-upload-section">
            <p className="section-heading">Upload PDF Receipts</p>
            <ReceiptUploadArea
              onUpload={handleUpload}
              processing={processing}
              disabled={txnLoading || folderStatus === 'SUBMITTED'}
            />
          </div>
        )}

        {/* Processed expenses table */}
        {processedExpenses.length > 0 && (
          <div className="processed-expenses-section">
            <p className="section-heading">
              Processed Expenses
              <span className="section-count">
                &nbsp;({processedExpenses.filter(e => e.matchedTxnId).length}/{processedExpenses.length} matched to card)
              </span>
            </p>
            <ProcessedExpensesTable expenses={processedExpenses} />
          </div>
        )}

        {/* Policy warnings */}
        {warnings.length > 0 && (
          <div className="warnings-section">
            <p className="section-heading">Policy Warnings ({warnings.length})</p>
            <WarningsList warnings={warnings} />
          </div>
        )}

        {/* Submit bar */}
        {folderStatus !== 'SUBMITTED' && processedExpenses.length > 0 && (
          <div className="submit-bar">
            <p className="submit-bar-info">
              {hasErrors
                ? '⛔ Fix the errors above before submitting.'
                : warnings.length > 0
                ? `⚠️ ${warnings.length} warning${warnings.length !== 1 ? 's' : ''} — you can still submit.`
                : '✅ All checks passed. Ready to submit.'}
            </p>
            <Button kind="secondary" onClick={() => navigate('/')} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={!canSubmit}>
              {submitting ? 'Submitting…' : 'Submit to SAP Concur'}
            </Button>
          </div>
        )}

      </div>

      {/* ── Chat panel ── */}
      <ChatPanel messages={chatMessages} onMessage={addAgentMessage} folderStatus={folderStatus} />

    </div>
  );
}

export default ReportFolderPage;
