import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createReport } from '../services/reportService';
import './CreateReportPage.css';

const POLICIES = [
  { value: 'STANDARD', label: 'Standard - Domestic Travel' },
  { value: 'EXECUTIVE', label: 'Executive - Senior / International' },
];

const CATEGORIES = [
  { value: 'TRAVEL', label: 'Travel' },
  { value: 'CONFERENCE_TRADESHOW_CUSTOMER', label: 'Conference / Tradeshow (Customer)' },
  { value: 'CONFERENCE_TRADESHOW_NON_CUSTOMER', label: 'Conference / Tradeshow (Internal)' },
  { value: 'CORPORATE_EVENT_RECOGNITION', label: 'Corporate Event / Recognition' },
  { value: 'CUSTOMER_CLIENT_RELATED_TRAVEL', label: 'Customer / Client Related Travel' },
  { value: 'EDUCATION_SEMINAR', label: 'Education / Seminar' },
  { value: 'NON_TRAVEL_EXPENSES', label: 'Non-Travel Expenses' },
];

const EMPLOYEES = [
  { value: 'EMP001', label: 'Priya Sharma', detail: 'Consulting' },
  { value: 'EMP002', label: 'Arjun Mehta', detail: 'Engineering' },
  { value: 'EMP003', label: 'Kavita Nair', detail: 'Consulting' },
  { value: 'EMP004', label: 'Rohan Desai', detail: 'Engineering' },
];

const EMPLOYEE_POLICY_MAP = { EMP001: 'STANDARD', EMP002: 'STANDARD', EMP003: 'EXECUTIVE', EMP004: 'EXECUTIVE' };

function CreateReportPage() {
  const navigate = useNavigate();
  const [fields, setFields] = useState({ employeeId: 'EMP001', reportName: '', businessPurpose: '', policy: 'STANDARD', reportCategory: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isValid = fields.reportName.trim() && fields.businessPurpose.trim() && fields.policy && fields.reportCategory;
  const selectedEmployee = EMPLOYEES.find(employee => employee.value === fields.employeeId);

  function updateField(field, value) {
    setFields(previous => field === 'employeeId'
      ? { ...previous, employeeId: value, policy: EMPLOYEE_POLICY_MAP[value] || previous.policy }
      : { ...previous, [field]: value });
    setError('');
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!isValid) return;
    setLoading(true);
    setError('');
    try {
      const data = await createReport(fields);
      navigate(`/report/${data.reportId}`, { state: fields });
    } catch (requestError) {
      setError(requestError.response?.data?.error || requestError.response?.data?.detail || 'Unable to create the expense report. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="roam-shell">
      <aside className="roam-sidebar">
        <div className="roam-brand"><span className="roam-mark">r</span><span>roam</span></div>
        <nav className="roam-nav" aria-label="Primary navigation">
          <button type="button" className="roam-nav-item is-active"><span className="nav-glyph">▦</span>Dashboard</button>
          <button type="button" className="roam-nav-item"><span className="nav-glyph">+</span>New claim</button>
          <button type="button" className="roam-nav-item"><span className="nav-glyph">▤</span>My claims</button>
          <button type="button" className="roam-nav-item"><span className="nav-glyph">✈</span>Trips</button>
          <button type="button" className="roam-nav-item"><span className="nav-glyph">□</span>Receipts</button>
        </nav>
        <div className="roam-sidebar-foot"><span className="ai-star">*</span><div><strong>Roam AI</strong><small>Your expense assistant</small></div></div>
      </aside>

      <main className="roam-main">
        <header className="roam-topbar"><span className="roam-crumb">Overview <i>•</i> Expense workspace</span><div className="roam-profile">PS</div></header>
        <div className="dashboard-content">
          <section className="dashboard-intro">
            <div><p className="dashboard-eyebrow">EXPENSE WORKSPACE</p><h1>Good morning, {selectedEmployee?.label.split(' ')[0]}</h1><p>Start a claim and let the copilot prepare it for you.</p></div>
            <span className="dashboard-date">Travel claims</span>
          </section>

          <section className="dashboard-kpis" aria-label="Expense report summary">
            <article className="dashboard-kpi mint"><span className="kpi-symbol">₹</span><p>Expense reports</p><strong>Ready to start</strong><small>Create a report in minutes</small></article>
            <article className="dashboard-kpi lilac"><span className="kpi-symbol">◷</span><p>Receipt processing</p><strong>AI-assisted</strong><small>PDF extraction and matching</small></article>
            <article className="dashboard-kpi peach"><span className="kpi-symbol">✓</span><p>Policy checks</p><strong>Built in</strong><small>Review warnings before submit</small></article>
          </section>

          <section className="claim-workspace">
            <div className="workspace-copy"><p className="dashboard-eyebrow">NEW REIMBURSEMENT</p><h2>Start a travel claim</h2><p>Enter the business context first. Corporate card transactions and receipt tools will be available in the claim folder.</p><div className="workflow-note"><span>1</span> Claim details <b>2</b> Upload receipts <b>3</b> Review and submit</div></div>
            <form className="claim-form" onSubmit={handleSubmit} noValidate>
              {error && <div className="form-error" role="alert">{error}</div>}
              <label>Employee<select value={fields.employeeId} onChange={event => updateField('employeeId', event.target.value)}>{EMPLOYEES.map(employee => <option key={employee.value} value={employee.value}>{employee.value} - {employee.label} ({employee.detail})</option>)}</select></label>
              <label>Report name<input value={fields.reportName} onChange={event => updateField('reportName', event.target.value)} placeholder="e.g. Bengaluru client visit - July 2026" required /></label>
              <label>Business purpose<textarea value={fields.businessPurpose} onChange={event => updateField('businessPurpose', event.target.value)} placeholder="e.g. Client workshop at IBM Garage, Bengaluru" rows="3" required /></label>
              <div className="claim-form-row"><label>Travel policy<select value={fields.policy} onChange={event => updateField('policy', event.target.value)}>{POLICIES.map(policy => <option key={policy.value} value={policy.value}>{policy.label}</option>)}</select></label><label>Report category<select value={fields.reportCategory} onChange={event => updateField('reportCategory', event.target.value)} required><option value="">Select category</option>{CATEGORIES.map(category => <option key={category.value} value={category.value}>{category.label}</option>)}</select></label></div>
              <button className="roam-primary" type="submit" disabled={!isValid || loading}>{loading ? 'Creating report...' : 'Create expense report'} <span>→</span></button>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}

export default CreateReportPage;
