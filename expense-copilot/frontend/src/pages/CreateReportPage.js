import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  TextInput,
  TextArea,
  Select,
  SelectItem,
  Button,
  InlineNotification,
  Stack,
  Tile,
} from '@carbon/react';
import { createReport } from '../services/reportService';
import './CreateReportPage.css';

// Matches exactly what concur-stub seed.py has seeded
const POLICIES = [
  { value: 'STANDARD',  label: 'Standard — Domestic Travel (EMP001, EMP002)' },
  { value: 'EXECUTIVE', label: 'Executive — Senior / International (EMP003, EMP004)' },
];

const CATEGORIES = [
  { value: 'TRAVEL',                          label: 'Travel' },
  { value: 'CONFERENCE_TRADESHOW_CUSTOMER',   label: 'Conference / Tradeshow (Customer)' },
  { value: 'CONFERENCE_TRADESHOW_NON_CUSTOMER', label: 'Conference / Tradeshow (Internal)' },
  { value: 'CORPORATE_EVENT_RECOGNITION',     label: 'Corporate Event / Recognition' },
  { value: 'CUSTOMER_CLIENT_RELATED_TRAVEL',  label: 'Customer / Client Related Travel' },
  { value: 'EDUCATION_SEMINAR',               label: 'Education / Seminar' },
  { value: 'NON_TRAVEL_EXPENSES',             label: 'Non-Travel Expenses' },
];

// Employee profiles — matches seed.py exactly
// EMP001 Priya Sharma = STANDARD | EMP002 Arjun Mehta = STANDARD
// EMP003 Kavita Nair  = EXECUTIVE | EMP004 Rohan Desai = EXECUTIVE
const EMPLOYEES = [
  { value: 'EMP001', label: 'EMP001 — Priya Sharma (Consulting, STANDARD)' },
  { value: 'EMP002', label: 'EMP002 — Arjun Mehta (Engineering, STANDARD)' },
  { value: 'EMP003', label: 'EMP003 — Kavita Nair (Consulting, EXECUTIVE)' },
  { value: 'EMP004', label: 'EMP004 — Rohan Desai (Engineering, EXECUTIVE)' },
];

// Auto-fill policy based on selected employee
const EMPLOYEE_POLICY_MAP = {
  EMP001: 'STANDARD',
  EMP002: 'STANDARD',
  EMP003: 'EXECUTIVE',
  EMP004: 'EXECUTIVE',
};

function CreateReportPage() {
  const navigate = useNavigate();

  const [fields, setFields] = useState({
    employeeId: 'EMP001',
    reportName: '',
    businessPurpose: '',
    policy: 'STANDARD',
    reportCategory: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const isValid =
    fields.reportName.trim() &&
    fields.businessPurpose.trim() &&
    fields.policy &&
    fields.reportCategory;

  function handleChange(field, value) {
    if (field === 'employeeId') {
      // Auto-set policy when employee changes
      setFields(prev => ({
        ...prev,
        employeeId: value,
        policy: EMPLOYEE_POLICY_MAP[value] || prev.policy,
      }));
    } else {
      setFields(prev => ({ ...prev, [field]: value }));
    }
    if (error) setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await createReport({
        employeeId:      fields.employeeId,
        reportName:      fields.reportName,
        businessPurpose: fields.businessPurpose,
        policy:          fields.policy,
        reportCategory:  fields.reportCategory,
      });
      navigate(`/report/${data.reportId}`, {
        state: {
          employeeId:      fields.employeeId,
          reportName:      fields.reportName,
          businessPurpose: fields.businessPurpose,
          policy:          fields.policy,
          reportCategory:  fields.reportCategory,
        }
      });
    } catch (err) {
      const msg = err.response?.data?.error
        || err.response?.data?.detail
        || 'Failed to create report. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="create-report-page">
      <div className="create-report-header">
        <p className="create-report-subtitle">Powered by watsonx Orchestrate</p>
        <h1 className="create-report-title">New Expense Report</h1>
        <p className="create-report-desc">
          Fill in the details below to create your expense report. Once created,
          your corporate card transactions will load automatically.
        </p>
      </div>

      <Tile className="create-report-tile">
        <form onSubmit={handleSubmit} noValidate>
          <Stack gap={6}>

            {error && (
              <InlineNotification
                kind="error"
                title="Error"
                subtitle={error}
                hideCloseButton
              />
            )}

            {/* Employee selector — drives policy auto-fill */}
            <Select
              id="employeeId"
              labelText="Employee"
              value={fields.employeeId}
              onChange={e => handleChange('employeeId', e.target.value)}
              required
            >
              {EMPLOYEES.map(emp => (
                <SelectItem key={emp.value} value={emp.value} text={emp.label} />
              ))}
            </Select>

            <TextInput
              id="reportName"
              labelText="Report Name"
              placeholder="e.g. Bengaluru Client Visit — July 2026"
              value={fields.reportName}
              onChange={e => handleChange('reportName', e.target.value)}
              required
            />

            <TextArea
              id="businessPurpose"
              labelText="Business Purpose"
              placeholder="e.g. Client workshop at IBM Garage, Bengaluru"
              value={fields.businessPurpose}
              onChange={e => handleChange('businessPurpose', e.target.value)}
              rows={3}
              required
            />

            {/* Policy — auto-filled from employee, still editable */}
            <Select
              id="policy"
              labelText="Travel Policy (auto-filled from employee)"
              value={fields.policy}
              onChange={e => handleChange('policy', e.target.value)}
              required
            >
              <SelectItem value="" text="Select a policy" />
              {POLICIES.map(p => (
                <SelectItem key={p.value} value={p.value} text={p.label} />
              ))}
            </Select>

            <Select
              id="reportCategory"
              labelText="Report Category"
              value={fields.reportCategory}
              onChange={e => handleChange('reportCategory', e.target.value)}
              required
            >
              <SelectItem value="" text="Select a category" />
              {CATEGORIES.map(c => (
                <SelectItem key={c.value} value={c.value} text={c.label} />
              ))}
            </Select>

            <Button type="submit" disabled={!isValid || loading}>
              {loading ? 'Creating report…' : 'Create Expense Report'}
            </Button>

          </Stack>
        </form>
      </Tile>
    </div>
  );
}

export default CreateReportPage;
