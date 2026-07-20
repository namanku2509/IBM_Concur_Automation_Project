/* ─────────────────────────────────────────────────────────────────────────────
   Roam — IBM Travel & Expense  |  Unified SPA  |  app.js
   All data comes from the BFF at /api/travel/* and /api/report/*
───────────────────────────────────────────────────────────────────────────── */

const EMPLOYEE_ID = 'EMP001';
const BFF         = '';          // same origin — nginx / BFF serves this file

// ── State ──────────────────────────────────────────────────────────────────
let S = { bookings: [], hotelBookings: [], claims: [] };

// ── DOM refs ───────────────────────────────────────────────────────────────
const content    = document.getElementById('content');
const breadcrumb = document.getElementById('breadcrumb');
const toast      = document.getElementById('toast');
const drawer     = document.getElementById('drawer');
const drawerInner= document.getElementById('drawerInner');
const backdrop   = document.getElementById('drawerBackdrop');

// ── Utilities ──────────────────────────────────────────────────────────────
function money(v) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(v || 0);
}
function esc(v) {
  const d = document.createElement('span'); d.textContent = String(v ?? ''); return d.innerHTML;
}
function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}
function stars(n) { return '★'.repeat(n) + '☆'.repeat(5 - n); }

function toast_(title, msg, type = 'success') {
  document.getElementById('toastTitle').textContent = title;
  document.getElementById('toastMsg').textContent   = msg;
  document.getElementById('toastIcon').textContent  = type === 'error' ? '✕' : '✓';
  toast.className = `toast show ${type}`;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove('show'), 5000);
}

async function api(path, opts = {}) {
  const res  = await fetch(`${BFF}/api/travel${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function bff(path, opts = {}) {
  const res  = await fetch(`${BFF}/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...opts,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || data.detail || `HTTP ${res.status}`);
  return data;
}

async function refresh() {
  const [state, reports] = await Promise.allSettled([
    api(`/state?employeeId=${EMPLOYEE_ID}`),
    fetch(`${BFF}/api/report/all?employeeId=${EMPLOYEE_ID}`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : [])
      .catch(() => []),
  ]);
  S = state.status === 'fulfilled' ? state.value : { bookings: [], hotelBookings: [], claims: [] };
  const raw = reports.status === 'fulfilled' ? reports.value : [];
  S._expenseReports = Array.isArray(raw) ? raw : [];
}

// ── Drawer ─────────────────────────────────────────────────────────────────
function openDrawer(html) {
  drawerInner.innerHTML = `
    <button class="drawer-close" id="drawerClose">✕</button>
    ${html}`;
  drawer.classList.add('open');
  backdrop.classList.add('show');
  document.getElementById('drawerClose').onclick = closeDrawer;
}
function closeDrawer() {
  drawer.classList.remove('open');
  backdrop.classList.remove('show');
}
backdrop.onclick = closeDrawer;

// ── Navigation ─────────────────────────────────────────────────────────────
const PAGE_LABELS = {
  'dashboard':  'Overview',
  'new-claim':  'New claim',
  'my-claims':  'My claims',
  'book-flight':'Book flight',
  'book-hotel': 'Book hotel',
};

function nav(page) {
  document.querySelectorAll('.nav-item[data-page]').forEach(b =>
    b.classList.toggle('active', b.dataset.page === page));
  breadcrumb.textContent = PAGE_LABELS[page] || page;
  closeDrawer();
  PAGES[page]?.();
}

document.querySelectorAll('.nav-item[data-page]').forEach(b => {
  b.onclick = () => nav(b.dataset.page);
});

document.getElementById('refreshBtn').onclick = async () => {
  await refresh();
  const active = document.querySelector('.nav-item.active')?.dataset.page || 'dashboard';
  nav(active);
  toast_('Refreshed', 'Data is up to date.');
};

// ── Cross-tab refresh via BroadcastChannel ─────────────────────────────────
// The React expense folder posts 'report-submitted' when a report is submitted.
// We listen here and silently refresh state + re-render the active page.
if (typeof BroadcastChannel !== 'undefined') {
  const _bc = new BroadcastChannel('roam-expense');
  _bc.onmessage = async (e) => {
    if (e.data?.type === 'report-submitted') {
      await refresh();
      const active = document.querySelector('.nav-item.active')?.dataset.page || 'dashboard';
      nav(active);
      toast_('Claims updated ✓', `${e.data.reportId || 'New report'} is now in My claims.`);
    }
  };
}

document.getElementById('aiBtn').onclick = () => {};

// ── Search (filters visible claim/booking rows) ────────────────────────────
document.getElementById('searchInput').oninput = function () {
  const q = this.value.toLowerCase();
  content.querySelectorAll('[data-searchable]').forEach(el => {
    el.style.display = el.dataset.searchable.toLowerCase().includes(q) ? '' : 'none';
  });
};

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE: DASHBOARD
═══════════════════════════════════════════════════════════════════════════ */
function pageDashboard() {
  const allBookings    = [...(S.bookings || []), ...(S.hotelBookings || [])];
  const expenseReports = S._expenseReports || [];
  const claimed        = (S.claims || []).length + expenseReports.filter(r => r.status === 'SUBMITTED').length;
  const unclaimed      = allBookings.filter(b => !b.claimId).length;
  const totalSpend     = allBookings.reduce((s, b) => s + (b.totalPrice || 0), 0);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  content.innerHTML = `
    <div class="page-pad">
      <div class="page-header">
        <div>
          <p class="eyebrow">IBM TRAVEL &amp; EXPENSE</p>
          <h1>${greeting}, Priya ✦</h1>
          <p class="sub">Everything in one place — book, claim, track.</p>
        </div>
        <button class="btn-primary" id="dashNewClaim">+ New claim</button>
      </div>

      <div class="stat-row">
        <div class="stat-card" id="statBookings">
          <span class="stat-label">Confirmed bookings</span>
          <span class="stat-num">${allBookings.length}</span>
          <span class="stat-sub">${unclaimed} awaiting claim</span>
        </div>
        <div class="stat-card" id="statClaims">
          <span class="stat-label">Submitted claims</span>
          <span class="stat-num">${claimed}</span>
          <span class="stat-sub">via expense system</span>
        </div>
        <div class="stat-card" id="statSpend">
          <span class="stat-label">Total travel spend</span>
          <span class="stat-num">${money(totalSpend)}</span>
          <span class="stat-sub">across all bookings</span>
        </div>
      </div>

      <div class="dash-grid">
        <!-- Recent bookings -->
        <section class="dash-panel">
          <div class="panel-hd">
            <h2>Recent bookings</h2>
            <button class="btn-link" id="dashViewBookings">View all →</button>
          </div>
          ${recentBookingsHTML(allBookings)}
        </section>

        <!-- Quick actions -->
        <section class="dash-panel">
          <div class="panel-hd"><h2>Quick actions</h2></div>
          <div class="quick-actions">
            <button class="qa-card" id="qaBkFlight">
              <svg viewBox="0 0 24 24"><path d="m22 16-8.5-4.5V5.2a1.5 1.5 0 0 0-3 0v6.3L2 16v2l8.5-2v3.5l-2 1.5v1h7v-1l-2-1.5V16l8.5 2v-2Z"/></svg>
              <strong>Book flight</strong>
              <span>Search &amp; book a corporate fare</span>
            </button>
            <button class="qa-card" id="qaBkHotel">
              <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="18" rx="1"/><path d="M9 21V12h6v9M2 9h20"/></svg>
              <strong>Book hotel</strong>
              <span>Find policy-approved hotels</span>
            </button>
            <button class="qa-card" id="qaNewClaim">
              <svg viewBox="0 0 24 24"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"/><path d="M9 8h6M9 12h4"/></svg>
              <strong>New claim</strong>
              <span>Upload receipts &amp; submit</span>
            </button>
            <button class="qa-card" id="qaMyClaims">
              <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8 12 2.5 2.5L16 9"/></svg>
              <strong>My claims</strong>
              <span>Track submitted reports</span>
            </button>
          </div>
        </section>
      </div>

      <!-- Unclaimed bookings notice -->
      ${unclaimed > 0 ? `
      <div class="notice">
        <span>⚠️</span>
        <span>You have <b>${unclaimed} confirmed booking${unclaimed !== 1 ? 's' : ''}</b> without a submitted claim.
          <button class="btn-link" id="dashGoNewClaim">Create a claim now →</button></span>
      </div>` : ''}
    </div>`;

  document.getElementById('dashNewClaim').onclick    = () => nav('new-claim');
  document.getElementById('dashViewBookings').onclick = () => nav('my-claims');
  document.getElementById('qaBkFlight').onclick      = () => nav('book-flight');
  document.getElementById('qaBkHotel').onclick       = () => nav('book-hotel');
  document.getElementById('qaNewClaim').onclick      = () => nav('new-claim');
  document.getElementById('qaMyClaims').onclick      = () => nav('my-claims');
  const gncBtn = document.getElementById('dashGoNewClaim');
  if (gncBtn) gncBtn.onclick = () => nav('new-claim');

  // Clicking a recent booking opens its detail drawer
  content.querySelectorAll('[data-booking-id]').forEach(el => {
    el.onclick = () => {
      const b = allBookings.find(x => x.bookingId === el.dataset.bookingId);
      if (b) openBookingDrawer(b);
    };
  });
}

function recentBookingsHTML(bookings) {
  const recent = [...bookings].sort((a, b) => new Date(b.bookedAt) - new Date(a.bookedAt)).slice(0, 4);
  if (!recent.length) return '<p class="empty">No bookings yet. Book a flight or hotel to get started.</p>';
  return `<div class="booking-mini-list">${recent.map(b => {
    const isFlight = b.type === 'FLIGHT';
    const label    = isFlight ? `${b.flight.from} → ${b.flight.to}` : b.hotel.name;
    const detail   = isFlight ? `${b.flight.airline} · ${b.travelDate}` : `${b.hotel.cityName} · ${b.checkin}`;
    return `<div class="booking-mini" data-booking-id="${esc(b.bookingId)}" data-searchable="${esc(label)}">
      <span class="bm-icon ${isFlight ? 'bm-flight' : 'bm-hotel'}">${isFlight ? '✈' : '🏨'}</span>
      <div class="bm-body">
        <strong>${esc(label)}</strong>
        <span>${esc(detail)}</span>
      </div>
      <div class="bm-right">
        <strong>${money(b.totalPrice)}</strong>
        ${b.claimId ? '<span class="badge badge-green">Claimed</span>' : '<span class="badge badge-amber">Unclaimed</span>'}
      </div>
    </div>`;
  }).join('')}</div>`;
}

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE: NEW CLAIM
   Two-column: form left, live pipeline status panel right.
═══════════════════════════════════════════════════════════════════════════ */

// Pipeline steps shown in the right panel
const CLAIM_PIPELINE = [
  { id: 'create',   label: 'Report created',         desc: 'Shell report registered in the system' },
  { id: 'txn',      label: 'Card transactions loaded', desc: 'Corporate card feed fetched from Concur' },
  { id: 'ocr',      label: 'OCR processing',           desc: 'Docling extracts text from PDF receipts' },
  { id: 'ai',       label: 'AI field extraction',      desc: 'Ollama LLM extracts vendor, amount, date' },
  { id: 'match',    label: 'Transaction matching',     desc: 'Fuzzy match receipts to card transactions' },
  { id: 'submit',   label: 'Submitted',                desc: 'Expense report posted and locked' },
];

function pipelineHTML(activeId, doneIds = [], errorId = null) {
  return CLAIM_PIPELINE.map((step, i) => {
    const isDone   = doneIds.includes(step.id);
    const isActive = step.id === activeId;
    const isError  = step.id === errorId;
    const state    = isError ? 'error' : isDone ? 'done' : isActive ? 'active' : 'idle';
    const icon     = isDone ? '✓' : isError ? '✕' : isActive ? '⟳' : (i + 1);
    const isLast   = i === CLAIM_PIPELINE.length - 1;
    return `
      <div class="ps-step ps-step--${state}">
        <div class="ps-dot-col">
          <div class="ps-dot ps-dot--${state}">${icon}</div>
          ${!isLast ? `<div class="ps-connector ${isDone ? 'ps-connector--done' : ''}"></div>` : ''}
        </div>
        <div class="ps-body">
          <span class="ps-label">${esc(step.label)}</span>
          <span class="ps-desc">${esc(step.desc)}</span>
        </div>
      </div>`;
  }).join('');
}

function pageNewClaim() {
  content.innerHTML = `
    <div class="page-pad page-narrow">
      <p class="eyebrow">EXPENSE REPORT</p>
      <h1>Start a new claim</h1>
      <p class="sub">Fill in the details below — the claim folder opens in a new tab where you can upload receipts and submit.</p>

      <div class="new-claim-layout">

        <!-- LEFT: form -->
        <div>
          <form class="claim-form" id="claimForm">
            <div class="form-error hidden" id="claimError"></div>

            <div class="field">
              <span>Employee</span>
              <div class="employee-static">
                <div class="avatar avatar-sm">PS</div>
                <span><strong>Priya Sharma</strong> &nbsp;<span class="muted">EMP001 · Consulting</span></span>
              </div>
            </div>

            <label class="field">
              <span>Report name <em>*</em></span>
              <input name="reportName" placeholder="e.g. Bengaluru client visit — July 2026" required />
            </label>

            <label class="field">
              <span>Business purpose <em>*</em></span>
              <textarea name="businessPurpose" rows="3" placeholder="e.g. Client workshop at IBM Garage, Bengaluru" required></textarea>
            </label>

            <div class="form-row">
              <label class="field">
                <span>Travel policy</span>
                <select name="policy" id="policySelect">
                  <option value="STANDARD">Standard — Domestic Travel</option>
                  <option value="EXECUTIVE">Executive — Senior / International</option>
                </select>
              </label>
              <label class="field">
                <span>Category <em>*</em></span>
                <select name="reportCategory" required>
                  <option value="">Select category</option>
                  <option value="TRAVEL">Travel</option>
                  <option value="CUSTOMER_CLIENT_RELATED_TRAVEL">Customer / Client Related Travel</option>
                  <option value="CONFERENCE_TRADESHOW_CUSTOMER">Conference / Tradeshow (Customer)</option>
                  <option value="CONFERENCE_TRADESHOW_NON_CUSTOMER">Conference / Tradeshow (Internal)</option>
                  <option value="CORPORATE_EVENT_RECOGNITION">Corporate Event / Recognition</option>
                  <option value="EDUCATION_SEMINAR">Education / Seminar</option>
                  <option value="NON_TRAVEL_EXPENSES">Non-Travel Expenses</option>
                </select>
              </label>
            </div>

            <button class="btn-primary" type="submit" id="claimSubmitBtn">Create &amp; open claim folder →</button>
          </form>
        </div>

        <!-- RIGHT: pipeline status -->
        <div class="pipeline-panel" id="pipelinePanel">
          <p class="pipeline-panel-title">Processing pipeline</p>
          <div class="pipeline-step-list" id="pipelineSteps">
            ${pipelineHTML(null, [], null)}
          </div>
          <div class="pipeline-hint" id="pipelineHint">
            Fill in the form and click <strong>Create &amp; open claim folder</strong>.<br>
            The pipeline will activate as you upload receipts in the claim folder.
          </div>
        </div>

      </div>
    </div>`;

  function setPipeline(activeId, doneIds, errorId, hint) {
    const el = document.getElementById('pipelineSteps');
    if (el) el.innerHTML = pipelineHTML(activeId, doneIds, errorId);
    const h = document.getElementById('pipelineHint');
    if (h && hint !== undefined) h.innerHTML = hint;
  }

  document.getElementById('claimForm').onsubmit = async (e) => {
    e.preventDefault();
    const btn = document.getElementById('claimSubmitBtn');
    const err = document.getElementById('claimError');
    const fd  = Object.fromEntries(new FormData(e.currentTarget));
    fd.employeeId = EMPLOYEE_ID;
    btn.disabled = true;
    btn.textContent = 'Creating…';
    err.classList.add('hidden');

    // Step 1: creating report
    setPipeline('create', [], null, 'Creating report shell in the system…');
    try {
      const data = await bff('/report', { method: 'POST', body: JSON.stringify(fd) });

      // Step 2: report created, txn fetch will happen in the folder
      setPipeline('txn', ['create'], null,
        `✓ Report <strong>${esc(data.reportId)}</strong> created.<br>
         Opening claim folder — card transactions will load automatically.`);

      toast_('Claim created ✓', `${data.reportId} — opening claim folder…`);

      const params = new URLSearchParams({
        reportId:        data.reportId,
        reportName:      fd.reportName,
        businessPurpose: fd.businessPurpose,
        policy:          fd.policy,
        reportCategory:  fd.reportCategory,
        employeeId:      fd.employeeId,
      });

      // Brief pause so user sees the pipeline update before the tab opens
      await new Promise(r => setTimeout(r, 600));
      setPipeline('txn', ['create'], null,
        `Claim folder opened in a new tab.<br>Upload receipts there to continue the pipeline.`);
      window.open(`http://localhost:3000/report/${data.reportId}?${params}`, '_blank');

      btn.disabled = false;
      btn.textContent = 'Create & open claim folder →';
    } catch (ex) {
      setPipeline(null, [], 'create', `❌ ${esc(ex.message)}`);
      err.textContent = ex.message;
      err.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'Create & open claim folder →';
    }
  };

  // Listen for BroadcastChannel events from the React folder to update
  // the pipeline steps in real-time as the user works in the other tab.
  if (typeof BroadcastChannel !== 'undefined') {
    const _pbc = new BroadcastChannel('roam-expense');
    _pbc.onmessage = (e) => {
      if (e.data?.type === 'pipeline-step') {
        const { step, done, hint } = e.data;
        setPipeline(step, done || [], null, hint || '');
      }
      if (e.data?.type === 'report-submitted') {
        setPipeline(null, ['create','txn','ocr','ai','match','submit'], null,
          `✅ Report <strong>${esc(e.data.reportId || '')}</strong> submitted successfully.<br>
           View it in <button class="btn-link" onclick="nav('my-claims')">My claims →</button>`);
      }
    };
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE: MY CLAIMS  — all bookings + submitted claims, click for full detail
═══════════════════════════════════════════════════════════════════════════ */
function pageMyClaims() {
  const allBookings = [
    ...(S.bookings || []).map(b => ({ ...b, _kind: 'FLIGHT' })),
    ...(S.hotelBookings || []).map(b => ({ ...b, _kind: 'HOTEL' })),
  ].sort((a, b) => new Date(b.bookedAt) - new Date(a.bookedAt));

  // Travel booking claims (created from flight/hotel confirmations)
  const travelClaims = [...(S.claims || [])].sort((a, b) =>
    new Date(b.submittedAt) - new Date(a.submittedAt));

  // Only SUBMITTED expense reports — drafts/in-review never appear here
  const expenseReports = [...(S._expenseReports || [])]
    .filter(r => r.status === 'SUBMITTED')
    .sort((a, b) => new Date(b.submittedAt) - new Date(a.submittedAt));

  // Combined count for "Submitted claims" section heading
  const totalSubmitted = travelClaims.length + expenseReports.length;

  content.innerHTML = `
    <div class="page-pad">
      <div class="page-header">
        <div>
          <p class="eyebrow">REIMBURSEMENTS</p>
          <h1>My claims</h1>
          <p class="sub">All bookings and submitted expense reports. Click any row for full details.</p>
        </div>
        <button class="btn-primary" id="mcNewClaim">+ New claim</button>
      </div>

      <!-- Confirmed bookings -->
      <section class="list-section">
        <h2 class="list-title">Confirmed bookings <span class="count">${allBookings.length}</span></h2>
        ${allBookings.length ? `
        <div class="list-table">
          <div class="list-head">
            <span>Trip / Hotel</span><span>Date</span><span>Amount</span><span>Claim status</span>
          </div>
          ${allBookings.map(b => {
            const label  = b._kind === 'FLIGHT' ? `${b.flight.from} → ${b.flight.to}` : b.hotel.name;
            const detail = b._kind === 'FLIGHT' ? `${b.flight.airline} ${b.flight.number}` : b.hotel.cityName;
            const date   = b._kind === 'FLIGHT' ? b.travelDate : b.checkin;
            return `<div class="list-row" data-searchable="${esc(label)} ${esc(detail)}" data-booking-id="${esc(b.bookingId)}">
              <span>
                <span class="row-icon ${b._kind === 'FLIGHT' ? 'ri-flight' : 'ri-hotel'}">${b._kind === 'FLIGHT' ? '✈' : '🏨'}</span>
                <span class="row-main">
                  <strong>${esc(label)}</strong>
                  <small>${esc(detail)}</small>
                </span>
              </span>
              <span>${esc(date)}</span>
              <span><strong>${money(b.totalPrice)}</strong></span>
              <span>${b.claimId
                ? `<span class="badge badge-green">Submitted</span>`
                : `<span class="badge badge-amber">Not claimed</span>`}
              </span>
            </div>`;
          }).join('')}
        </div>` : '<p class="empty">No bookings yet. Use Book flight or Book hotel to create one.</p>'}
      </section>

      <!-- Submitted claims (travel claims + expense reports) -->
      <section class="list-section">
        <h2 class="list-title">Submitted claims <span class="count">${totalSubmitted}</span></h2>
        ${totalSubmitted ? `
        <div class="list-table">
          <div class="list-head">
            <span>Report</span><span>Submitted</span><span>Total</span><span>Status</span>
          </div>
          ${travelClaims.map(c => `
            <div class="list-row" data-searchable="${esc(c.title)} ${esc(c.claimId)}" data-claim-id="${esc(c.claimId)}">
              <span>
                <span class="row-icon ri-claim">📋</span>
                <span class="row-main">
                  <strong>${esc(c.title)}</strong>
                  <small>${esc(c.claimId)}</small>
                </span>
              </span>
              <span>${fmt(c.submittedAt)}</span>
              <span><strong>${money(c.total)}</strong></span>
              <span><span class="badge badge-blue">Submitted</span></span>
            </div>`).join('')}
          ${expenseReports.map(r => {
            const total = (r.processedExpenses || []).reduce((s, e) => s + (e.amount || 0), 0);
            const statusBadge = r.status === 'SUBMITTED'
              ? '<span class="badge badge-green">Submitted</span>'
              : r.status === 'REVIEW'
              ? '<span class="badge badge-amber">In review</span>'
              : `<span class="badge badge-blue">${esc(r.status)}</span>`;
            return `<div class="list-row" data-searchable="${esc(r.reportName || r.reportId)} ${esc(r.reportId)}" data-expense-report-id="${esc(r.reportId)}">
              <span>
                <span class="row-icon ri-claim">🧾</span>
                <span class="row-main">
                  <strong>${esc(r.reportName || r.reportId)}</strong>
                  <small>${esc(r.reportId)} · ${esc(r.businessPurpose || '')}</small>
                </span>
              </span>
              <span>${fmt(r.submittedAt || r.createdAt)}</span>
              <span><strong>${total > 0 ? money(total) : '—'}</strong></span>
              <span>${statusBadge}</span>
            </div>`;
          }).join('')}
        </div>` : '<p class="empty">No claims submitted yet.</p>'}
      </section>
    </div>`;

  document.getElementById('mcNewClaim').onclick = () => nav('new-claim');

  // Booking row → drawer
  content.querySelectorAll('[data-booking-id]').forEach(el => {
    el.onclick = () => {
      const allB = [...(S.bookings || []), ...(S.hotelBookings || [])];
      const b = allB.find(x => x.bookingId === el.dataset.bookingId);
      if (b) openBookingDrawer(b);
    };
  });

  // Travel claim row → drawer
  content.querySelectorAll('[data-claim-id]').forEach(el => {
    el.onclick = () => {
      const c = (S.claims || []).find(x => x.claimId === el.dataset.claimId);
      if (c) openClaimDrawer(c);
    };
  });

  // Expense report row → summary drawer
  content.querySelectorAll('[data-expense-report-id]').forEach(el => {
    el.onclick = () => {
      const r = (S._expenseReports || []).find(x => x.reportId === el.dataset.expenseReportId);
      if (r) openExpenseReportDrawer(r);
    };
  });
}

/* ═══════════════════════════════════════════════════════════════════════════
   DRAWER: Expense report summary
   Shows report metadata, every submitted expense, and any policy justifications.
═══════════════════════════════════════════════════════════════════════════ */
function openExpenseReportDrawer(r) {
  const POLICY_LABELS = { STANDARD: 'Standard', EXECUTIVE: 'Executive' };
  const CAT_LABELS = {
    TRAVEL: 'Travel',
    CUSTOMER_CLIENT_RELATED_TRAVEL: 'Customer / Client Travel',
    CONFERENCE_TRADESHOW_CUSTOMER:  'Conference (Customer)',
    CONFERENCE_TRADESHOW_NON_CUSTOMER: 'Conference (Internal)',
    CORPORATE_EVENT_RECOGNITION:    'Corporate Event',
    EDUCATION_SEMINAR:              'Education / Seminar',
    NON_TRAVEL_EXPENSES:            'Non-Travel',
  };
  const TYPE_COLORS = {
    FLIGHT: 'flight', HOTEL: 'hotel', MEAL: 'meal', MEALS: 'meal',
    TAXI: 'taxi', REGISTRATION: 'taxi',
  };
  const expenses = (r.processedExpenses || []).filter(e => e.status !== 'error');
  const total    = expenses.reduce((s, e) => s + (e.amount || 0), 0);
  const matched  = expenses.filter(e => e.matchedTxnId).length;
  const cash     = expenses.filter(e => !e.matchedTxnId && e.status !== 'duplicate').length;

  // Collect all justifications stored on the report
  const justs = r.policyJustifications || {};

  // Build expense rows HTML
  const expenseRowsHTML = expenses.length
    ? `<div class="report-drawer-expense">
        ${expenses.map(e => {
          const typeKey = (e.expenseType || 'OTHER').toUpperCase();
          const cls     = TYPE_COLORS[typeKey] || '';
          return `<div class="rde-row">
            <span class="rde-type rde-type--${cls}">${esc(typeKey === 'MEALS' ? 'MEAL' : typeKey)}</span>
            <span class="rde-vendor">${esc(e.vendor || '—')}</span>
            <span class="rde-amount">${money(e.amount)}</span>
            <span class="rde-match ${e.matchedTxnId ? 'rde-match--card' : 'rde-match--cash'}">
              ${e.matchedTxnId ? `● ${esc(e.matchedTxnId)}` : '○ Cash'}
            </span>
          </div>`;
        }).join('')}
      </div>`
    : '<p class="empty">No processed expenses on this report.</p>';

  // Build justifications section
  const justKeys = Object.keys(justs).filter(k => justs[k]?.trim());
  const justsHTML = justKeys.length
    ? `<div class="drawer-section">
        <p class="eyebrow">Policy exception justifications</p>
        ${justKeys.map(k => `
          <div class="justification-item">
            <span class="ji-rule">Exception ${esc(k)}</span>
            <span class="ji-text">${esc(justs[k])}</span>
          </div>`).join('')}
      </div>`
    : '';

  const statusBadgeClass = r.status === 'SUBMITTED' ? 'badge-green'
    : r.status === 'REVIEW' ? 'badge-amber' : 'badge-blue';

  openDrawer(`
    <div class="drawer-content">
      <p class="eyebrow">EXPENSE REPORT</p>
      <h2>${esc(r.reportName || r.reportId)}</h2>
      <span class="badge ${statusBadgeClass}" style="margin-bottom:16px;display:inline-block">${esc(r.status)}</span>

      <!-- Meta grid -->
      <div class="report-drawer-meta">
        <div class="report-drawer-meta-item">
          <span class="rdi-label">Report ID</span>
          <span class="rdi-value">${esc(r.reportId)}</span>
        </div>
        <div class="report-drawer-meta-item">
          <span class="rdi-label">Employee</span>
          <span class="rdi-value">${esc(r.employeeId || EMPLOYEE_ID)}</span>
        </div>
        <div class="report-drawer-meta-item">
          <span class="rdi-label">Policy</span>
          <span class="rdi-value">${esc(POLICY_LABELS[r.policy] || r.policy || '—')}</span>
        </div>
        <div class="report-drawer-meta-item">
          <span class="rdi-label">Category</span>
          <span class="rdi-value">${esc(CAT_LABELS[r.reportCategory] || r.reportCategory || '—')}</span>
        </div>
        <div class="report-drawer-meta-item">
          <span class="rdi-label">Created</span>
          <span class="rdi-value">${fmt(r.createdAt)}</span>
        </div>
        <div class="report-drawer-meta-item">
          <span class="rdi-label">Submitted</span>
          <span class="rdi-value">${r.submittedAt ? fmt(r.submittedAt) : '—'}</span>
        </div>
      </div>

      <p style="font-size:12px;color:#68788a;margin-bottom:12px">${esc(r.businessPurpose || '')}</p>

      <!-- Summary bar -->
      <div class="drawer-section" style="padding-top:12px;margin-top:0;border-top:none">
        <div style="display:flex;gap:18px;margin-bottom:14px;flex-wrap:wrap">
          <div><span style="font-size:11px;color:#7a9080;text-transform:uppercase;font-weight:700">Total</span>
               <div style="font:700 20px Manrope;color:#1a2631">${money(total)}</div></div>
          <div><span style="font-size:11px;color:#7a9080;text-transform:uppercase;font-weight:700">Expenses</span>
               <div style="font:700 20px Manrope;color:#1a2631">${expenses.length}</div></div>
          <div><span style="font-size:11px;color:#7a9080;text-transform:uppercase;font-weight:700">Card matched</span>
               <div style="font:700 20px Manrope;color:#1e6b30">${matched}</div></div>
          <div><span style="font-size:11px;color:#7a9080;text-transform:uppercase;font-weight:700">Cash</span>
               <div style="font:700 20px Manrope;color:#68788a">${cash}</div></div>
        </div>
      </div>

      <!-- Expense rows -->
      <div class="drawer-section">
        <p class="eyebrow">Submitted expenses</p>
        ${expenseRowsHTML}
      </div>

      ${justsHTML}

      <!-- Open in React folder -->
      <div class="drawer-section">
        <button class="btn-secondary" style="width:100%" id="drawerOpenReactFolder">
          Open claim folder →
        </button>
      </div>
    </div>`);

  document.getElementById('drawerOpenReactFolder').onclick = () => {
    const params = new URLSearchParams({
      reportId:        r.reportId,
      reportName:      r.reportName      || '',
      businessPurpose: r.businessPurpose || '',
      policy:          r.policy          || 'STANDARD',
      reportCategory:  r.reportCategory  || '',
      employeeId:      r.employeeId      || EMPLOYEE_ID,
    });
    window.open(`http://localhost:3000/report/${r.reportId}?${params}`, '_blank');
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE: BOOK FLIGHT
═══════════════════════════════════════════════════════════════════════════ */
function pageBookFlight() {
  content.innerHTML = `
    <div class="page-pad">
      <p class="eyebrow">CORPORATE TRAVEL</p>
      <h1>Book a flight</h1>
      <p class="sub">Policy-compliant fares — charged directly to corporate card •••• 4242.</p>

      <div class="search-box" id="flightSearchBox">
        <form id="flightForm">
          <label class="field"><span>From</span>
            <input name="from" value="DEL" maxlength="3" style="text-transform:uppercase" required>
          </label>
          <label class="field"><span>To</span>
            <input name="to" placeholder="BOM" maxlength="3" style="text-transform:uppercase" required>
          </label>
          <label class="field"><span>Date</span>
            <input name="date" type="date" required>
          </label>
          <label class="field"><span>Cabin</span>
            <select name="cabin">
              <option value="ALL">All cabins</option>
              <option value="Economy">Economy</option>
              <option value="Business">Business</option>
            </select>
          </label>
          <label class="field"><span>Business purpose</span>
            <input name="purpose" placeholder="e.g. Client workshop" required>
          </label>
          <button class="btn-primary" type="submit">Search flights</button>
        </form>
      </div>
      <div id="flightResults"></div>
    </div>`;

  const di = content.querySelector('[name=date]');
  di.min = di.value = new Date().toISOString().slice(0, 10);

  content.querySelector('#flightForm').onsubmit = async e => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.currentTarget));
    fd.from = fd.from.toUpperCase().trim();
    fd.to   = fd.to.toUpperCase().trim();
    await showFlightResults(fd);
  };
}

async function showFlightResults(form) {
  const box = content.querySelector('#flightResults');
  box.innerHTML = '<p class="loading">Searching fares…</p>';
  try {
    const data = await api('/flights/search', { method: 'POST', body: JSON.stringify(form) });
    if (!data.flights?.length) {
      box.innerHTML = `<p class="empty error">No flights for <b>${esc(form.from)} → ${esc(form.to)}</b>.<br>Try: DEL→BOM, DEL→BLR, DEL→HYD, BOM→BLR, DEL→CCU.</p>`;
      return;
    }
    box.innerHTML = `
      <div class="results-hd">
        <h2>${esc(form.from)} → ${esc(form.to)}</h2>
        <span class="muted">${data.flights.length} flight${data.flights.length !== 1 ? 's' : ''} · ${esc(form.date)}</span>
      </div>
      <div class="flight-list">
        ${data.flights.map(f => `
          <article class="flight-card" data-flight='${esc(JSON.stringify(f))}'>
            <div class="fc-airline">
              <strong>${esc(f.airline)}</strong>
              <small>${esc(f.number)} · ${esc(f.aircraft || '')}</small>
            </div>
            <div class="fc-time">
              <span class="fc-dep">${esc(f.depart)}</span>
              <span class="fc-route"><span>${esc(f.from)}</span><i class="route-line"></i><span>${esc(f.to)}</span></span>
              <span class="fc-arr">${esc(f.arrive)}</span>
            </div>
            <div class="fc-dur">
              <span>${esc(f.duration)}</span>
              <small>${f.stops === 0 ? 'Non-stop' : f.stops + ' stop'}</small>
            </div>
            <div class="fc-cabin">
              <span class="badge ${f.cabin.toLowerCase().includes('business') ? 'badge-amber' : 'badge-green'}">${esc(f.badge)}</span>
              <small>${esc(f.cabin)}</small>
            </div>
            <div class="fc-price">
              <strong class="price">${money(f.price)}</strong>
              <button class="btn-primary btn-sm select-flight">Select</button>
            </div>
          </article>`).join('')}
      </div>`;

    box.querySelectorAll('.select-flight').forEach(btn => {
      btn.onclick = e => {
        e.stopPropagation();
        const f = JSON.parse(btn.closest('[data-flight]').dataset.flight);
        showSeatMap(f, form);
      };
    });
  } catch (err) {
    box.innerHTML = `<p class="empty error">${esc(err.message)}</p>`;
  }
}

async function showSeatMap(flight, form) {
  const box = content.querySelector('#flightResults');
  box.innerHTML = '<p class="loading">Loading seat map…</p>';
  let seatData;
  try {
    seatData = await api(`/flights/${encodeURIComponent(flight.id)}/seats`);
  } catch {
    showFlightConfirm(flight, null, form);
    return;
  }

  let selectedSeat = null;

  function renderSeatMap() {
    box.innerHTML = `
      <div class="seatmap-panel">
        <div class="seatmap-hd">
          <div>
            <h2>Choose your seat</h2>
            <p class="muted">${esc(flight.airline)} ${esc(flight.number)} · ${esc(flight.from)} → ${esc(flight.to)} · ${esc(flight.depart)}</p>
          </div>
          <button class="btn-link" id="skipSeat">Skip →</button>
        </div>

        <div class="seat-legend">
          <span><i class="sdot avail"></i> Available</span>
          <span><i class="sdot occ"></i> Occupied</span>
          <span><i class="sdot biz"></i> Business (+₹3,500)</span>
          <span><i class="sdot leg"></i> Extra legroom (+₹600)</span>
          <span><i class="sdot win"></i> Window</span>
        </div>

        <div class="seatmap-body">
          <div class="seat-col-labels">
            ${seatData.seatMap[0].seats.map(s => `<span>${esc(s.letter)}</span>`).join('')}
          </div>
          <div class="seat-rows" id="seatRows">
            ${seatData.seatMap.map(row => {
              const cls = row.type === 'business' ? 'row-biz' : row.type === 'extra_legroom' ? 'row-leg' : '';
              const seats6 = row.type !== 'business' && row.seats.length === 6;
              const seatBtns = (arr) => arr.map(s => seatBtn(s, row)).join('');
              return `<div class="seat-row ${cls}">
                <span class="row-num">${row.row}</span>
                ${seats6
                  ? seatBtns(row.seats.slice(0, 3)) + '<span class="aisle"></span>' + seatBtns(row.seats.slice(3))
                  : seatBtns(row.seats.slice(0, 2)) + '<span class="aisle"></span>' + seatBtns(row.seats.slice(2))}
              </div>`;
            }).join('')}
          </div>
        </div>

        <div class="seatmap-foot">
          <span id="seatInfo" class="muted">Select a seat or skip</span>
          <div style="display:flex;gap:10px">
            <button class="btn-secondary" id="backToFlights">← Flights</button>
            <button class="btn-primary" id="confirmSeat" disabled>Confirm seat →</button>
          </div>
        </div>
      </div>`;

    document.getElementById('skipSeat').onclick     = () => showFlightConfirm(flight, null, form);
    document.getElementById('backToFlights').onclick = () => showFlightResults(form);
    document.getElementById('confirmSeat').onclick  = () => showFlightConfirm(flight, selectedSeat, form);

    box.querySelectorAll('.seat-btn').forEach(btn => {
      btn.onclick = () => {
        box.querySelectorAll('.seat-btn.chosen').forEach(b => b.classList.remove('chosen'));
        btn.classList.add('chosen');
        selectedSeat = JSON.parse(btn.dataset.seat);
        const label = selectedSeat.price > 0 ? ` +${money(selectedSeat.price)}` : '';
        const type  = selectedSeat.extraLegroom ? 'Extra legroom' : 'Standard';
        document.getElementById('seatInfo').innerHTML = `<b>Seat ${esc(selectedSeat.seatId)}</b> — ${esc(type)}${label}`;
        document.getElementById('confirmSeat').disabled = false;
      };
    });
  }

  function seatBtn(s, row) {
    if (s.status === 'occupied')
      return `<button class="seat-btn occ" disabled>${esc(s.seatId)}</button>`;
    const cls = ['seat-btn',
      row.type === 'business' ? 'biz' : '',
      s.extraLegroom          ? 'leg' : '',
      s.window                ? 'win' : '',
    ].filter(Boolean).join(' ');
    return `<button class="${cls}" data-seat='${JSON.stringify(s)}'>${esc(s.seatId)}</button>`;
  }

  renderSeatMap();
}

function showFlightConfirm(flight, seat, form) {
  const box   = content.querySelector('#flightResults');
  const total = flight.price + (seat?.price || 0);

  box.innerHTML = `
    <div class="confirm-panel">
      <div class="confirm-hd">
        <h2>Confirm flight booking</h2>
        <p class="muted">Corporate card •••• 4242 will be charged ${money(total)}.</p>
      </div>
      <div class="confirm-route">
        <div class="ctime"><strong>${esc(flight.depart)}</strong><span>${esc(flight.from)}</span></div>
        <div class="cdash"><i class="route-line-lg"></i><small>${esc(flight.duration)} · Non-stop</small></div>
        <div class="ctime"><strong>${esc(flight.arrive)}</strong><span>${esc(flight.to)}</span></div>
      </div>
      <table class="ctable">
        <tr><td>Flight</td><td>${esc(flight.number)}</td></tr>
        <tr><td>Airline</td><td>${esc(flight.airline)}</td></tr>
        <tr><td>Date</td><td>${esc(form.date)}</td></tr>
        <tr><td>Cabin</td><td>${esc(flight.cabin)}</td></tr>
        <tr><td>Seat</td><td>${seat ? `${esc(seat.seatId)} (${seat.extraLegroom ? 'Extra legroom' : 'Standard'})` : '<em>Auto-assign</em>'}</td></tr>
        <tr><td>Business purpose</td><td>${esc(form.purpose)}</td></tr>
        <tr><td>Base fare</td><td>${money(flight.price)}</td></tr>
        ${seat?.price > 0 ? `<tr><td>Seat upgrade</td><td>${money(seat.price)}</td></tr>` : ''}
        <tr class="total-row"><td><strong>Total charged</strong></td><td><strong>${money(total)}</strong></td></tr>
      </table>
      <p class="card-notice">💳 Charged to corporate card •••• 4242 — appears in card transactions immediately.</p>
      <div class="confirm-actions">
        <button class="btn-secondary" id="backFromConfirm">← Back</button>
        <button class="btn-primary" id="doBookFlight">Confirm &amp; book →</button>
      </div>
    </div>`;

  document.getElementById('backFromConfirm').onclick = () => showSeatMap(flight, form);
  document.getElementById('doBookFlight').onclick    = async () => {
    const btn = document.getElementById('doBookFlight');
    btn.disabled = true; btn.textContent = 'Booking…';
    try {
      const bk = await api('/bookings', {
        method: 'POST',
        body: JSON.stringify({ employeeId: EMPLOYEE_ID, flight, travelDate: form.date, purpose: form.purpose, seat }),
      });
      await refresh();
      toast_('Flight booked ✈', `${bk.flight.airline} ${bk.flight.number} confirmed. Card txn ${bk.transactionId} ready.`);
      nav('my-claims');
    } catch (err) {
      toast_('Booking failed', err.message, 'error');
      btn.disabled = false; btn.textContent = 'Confirm & book →';
    }
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE: BOOK HOTEL
═══════════════════════════════════════════════════════════════════════════ */
function pageBookHotel() {
  const today    = new Date().toISOString().slice(0, 10);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

  content.innerHTML = `
    <div class="page-pad">
      <p class="eyebrow">CORPORATE TRAVEL</p>
      <h1>Book a hotel</h1>
      <p class="sub">Policy-approved properties — charged to corporate card •••• 4242.</p>

      <div class="search-box">
        <form id="hotelForm">
          <label class="field"><span>City / IATA</span>
            <input name="city" placeholder="BOM, BLR, DEL, HYD…" required>
          </label>
          <label class="field"><span>Check-in</span>
            <input name="checkin" type="date" value="${today}" min="${today}" required>
          </label>
          <label class="field"><span>Check-out</span>
            <input name="checkout" type="date" value="${tomorrow}" min="${tomorrow}" required>
          </label>
          <label class="field"><span>Business purpose</span>
            <input name="purpose" placeholder="e.g. Client offsite" required>
          </label>
          <button class="btn-primary" type="submit">Search hotels</button>
        </form>
      </div>
      <div id="hotelResults"></div>
    </div>`;

  const ci = content.querySelector('[name=checkin]');
  const co = content.querySelector('[name=checkout]');
  ci.onchange = () => { co.min = ci.value; if (co.value <= ci.value) co.value = ci.value; };

  content.querySelector('#hotelForm').onsubmit = async e => {
    e.preventDefault();
    const fd = Object.fromEntries(new FormData(e.currentTarget));
    await showHotelResults(fd);
  };
}

async function showHotelResults(form) {
  const box = content.querySelector('#hotelResults');
  box.innerHTML = '<p class="loading">Searching hotels…</p>';
  try {
    const data = await api('/hotels/search', { method: 'POST', body: JSON.stringify(form) });
    if (!data.hotels?.length) {
      box.innerHTML = `<p class="empty error">No hotels in <b>${esc(form.city)}</b>. Try: BOM, BLR, DEL, HYD.</p>`;
      return;
    }
    box.innerHTML = `
      <div class="results-hd">
        <h2>${esc(data.hotels[0]?.cityName || form.city)}</h2>
        <span class="muted">${data.nights} night${data.nights !== 1 ? 's' : ''} · ${data.hotels.length} propert${data.hotels.length !== 1 ? 'ies' : 'y'}</span>
      </div>
      <div class="hotel-list">
        ${data.hotels.map(h => `
          <article class="hotel-card">
            <div class="hc-img">${esc(h.image)}</div>
            <div class="hc-body">
              <div class="hc-top">
                <h3>${esc(h.name)}</h3>
                <span class="stars">${stars(h.stars)}</span>
              </div>
              <p class="hc-area">📍 ${esc(h.area)}</p>
              <p class="hc-rating">⭐ ${h.rating} / 5.0</p>
              <div class="amenity-row">${h.amenities.map(a => `<span class="amenity">${esc(a)}</span>`).join('')}</div>
            </div>
            <div class="hc-right">
              <span class="badge badge-green">${esc(h.badge)}</span>
              <div class="hc-price">
                <strong class="price">${money(h.nightlyRate)}</strong>
                <small>/night</small>
                <strong>${money(h.totalPrice)}</strong>
                <small>${data.nights} nights total</small>
              </div>
              <button class="btn-primary btn-sm" data-hotel='${esc(JSON.stringify(h))}'>Select</button>
            </div>
          </article>`).join('')}
      </div>`;

    box.querySelectorAll('[data-hotel]').forEach(btn => {
      btn.onclick = () => showHotelConfirm(JSON.parse(btn.dataset.hotel), form, data.nights);
    });
  } catch (err) {
    box.innerHTML = `<p class="empty error">${esc(err.message)}</p>`;
  }
}

function showHotelConfirm(hotel, form, nights) {
  const box   = content.querySelector('#hotelResults');
  const total = hotel.nightlyRate * nights;

  box.innerHTML = `
    <div class="confirm-panel">
      <div class="confirm-hd">
        <h2>Confirm hotel booking</h2>
        <p class="muted">Corporate card •••• 4242 will be charged ${money(total)}.</p>
      </div>
      <div class="hotel-confirm-hero">
        <span class="hch-img">${esc(hotel.image)}</span>
        <div>
          <strong>${esc(hotel.name)}</strong>
          <p class="muted">📍 ${esc(hotel.area)} · ${stars(hotel.stars)}</p>
        </div>
      </div>
      <table class="ctable">
        <tr><td>Check-in</td><td>${esc(form.checkin)}</td></tr>
        <tr><td>Check-out</td><td>${esc(form.checkout)}</td></tr>
        <tr><td>Duration</td><td>${nights} night${nights !== 1 ? 's' : ''}</td></tr>
        <tr><td>Nightly rate</td><td>${money(hotel.nightlyRate)}</td></tr>
        <tr><td>Rating</td><td>⭐ ${hotel.rating} / 5.0</td></tr>
        <tr><td>Amenities</td><td>${hotel.amenities.join(' · ')}</td></tr>
        <tr><td>Business purpose</td><td>${esc(form.purpose)}</td></tr>
        <tr class="total-row"><td><strong>Total charged</strong></td><td><strong>${money(total)}</strong></td></tr>
      </table>
      <p class="card-notice">💳 Charged to corporate card •••• 4242 — appears in card transactions immediately.</p>
      <div class="confirm-actions">
        <button class="btn-secondary" id="backFromHotelConfirm">← Back</button>
        <button class="btn-primary" id="doBookHotel">Confirm &amp; book →</button>
      </div>
    </div>`;

  document.getElementById('backFromHotelConfirm').onclick = () => showHotelResults(form);
  document.getElementById('doBookHotel').onclick          = async () => {
    const btn = document.getElementById('doBookHotel');
    btn.disabled = true; btn.textContent = 'Booking…';
    try {
      const bk = await api('/hotel-bookings', {
        method: 'POST',
        body: JSON.stringify({ employeeId: EMPLOYEE_ID, hotel, checkin: form.checkin, checkout: form.checkout, purpose: form.purpose }),
      });
      await refresh();
      toast_('Hotel booked 🏨', `${bk.hotel.name} — ${nights} night${nights !== 1 ? 's' : ''}. Card txn ${bk.transactionId} ready.`);
      nav('my-claims');
    } catch (err) {
      toast_('Booking failed', err.message, 'error');
      btn.disabled = false; btn.textContent = 'Confirm & book →';
    }
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   DRAWERS — full detail panels
═══════════════════════════════════════════════════════════════════════════ */
function openBookingDrawer(b) {
  const isFlight = b.type === 'FLIGHT';
  openDrawer(`
    <div class="drawer-content">
      <p class="eyebrow">${isFlight ? 'FLIGHT BOOKING' : 'HOTEL BOOKING'}</p>
      <h2>${isFlight ? `${b.flight.from} → ${b.flight.to}` : b.hotel.name}</h2>
      <span class="badge badge-green" style="margin-bottom:16px;display:inline-block">${esc(b.status)}</span>

      ${isFlight ? `
        <table class="ctable">
          <tr><td>Airline</td><td>${esc(b.flight.airline)}</td></tr>
          <tr><td>Flight</td><td>${esc(b.flight.number)}</td></tr>
          <tr><td>Route</td><td>${esc(b.flight.from)} → ${esc(b.flight.to)}</td></tr>
          <tr><td>Departure</td><td>${esc(b.flight.depart)}</td></tr>
          <tr><td>Arrival</td><td>${esc(b.flight.arrive)}</td></tr>
          <tr><td>Duration</td><td>${esc(b.flight.duration)}</td></tr>
          <tr><td>Cabin</td><td>${esc(b.flight.cabin)}</td></tr>
          <tr><td>Seat</td><td>${b.flight.selectedSeat ? esc(b.flight.selectedSeat) + ` (${esc(b.flight.seatType || '')})` : '—'}</td></tr>
          <tr><td>Travel date</td><td>${esc(b.travelDate)}</td></tr>
          <tr><td>Business purpose</td><td>${esc(b.purpose)}</td></tr>
          ${b.seatUpgrade > 0 ? `<tr><td>Seat upgrade</td><td>${money(b.seatUpgrade)}</td></tr>` : ''}
          <tr class="total-row"><td><strong>Total</strong></td><td><strong>${money(b.totalPrice)}</strong></td></tr>
        </table>` : `
        <table class="ctable">
          <tr><td>Hotel</td><td>${esc(b.hotel.name)}</td></tr>
          <tr><td>City</td><td>${esc(b.hotel.cityName)}</td></tr>
          <tr><td>Area</td><td>${esc(b.hotel.area)}</td></tr>
          <tr><td>Stars</td><td>${stars(b.hotel.stars)}</td></tr>
          <tr><td>Rating</td><td>⭐ ${b.hotel.rating} / 5.0</td></tr>
          <tr><td>Check-in</td><td>${esc(b.checkin)}</td></tr>
          <tr><td>Check-out</td><td>${esc(b.checkout)}</td></tr>
          <tr><td>Nights</td><td>${b.nights}</td></tr>
          <tr><td>Nightly rate</td><td>${money(b.hotel.nightlyRate)}</td></tr>
          <tr><td>Business purpose</td><td>${esc(b.purpose)}</td></tr>
          <tr class="total-row"><td><strong>Total</strong></td><td><strong>${money(b.totalPrice)}</strong></td></tr>
        </table>`}

      <div class="drawer-section">
        <p class="eyebrow">CARD TRANSACTION</p>
        <p><strong>${esc(b.transactionId)}</strong> — corporate card •••• 4242</p>
        <p class="muted" style="margin-top:4px">Booked ${fmt(b.bookedAt)}</p>
      </div>

      ${b.claimId ? `
        <div class="drawer-section">
          <p class="eyebrow">CLAIM</p>
          <p><span class="badge badge-green">Submitted</span> ${esc(b.claimId)}</p>
        </div>` : `
        <div class="drawer-section">
          <p class="muted">This booking has not been claimed yet.</p>
          <button class="btn-primary" style="margin-top:10px" id="drawerClaimBtn">Create claim for this trip</button>
        </div>`}
    </div>`);

  if (!b.claimId) {
    document.getElementById('drawerClaimBtn').onclick = async () => {
      try {
        const label = b.type === 'FLIGHT' ? `${b.flight.from} to ${b.flight.to}` : b.hotel.name;
        const claim = await api('/claims', {
          method: 'POST',
          body: JSON.stringify({ employeeId: EMPLOYEE_ID, bookingIds: [b.bookingId], title: `Business travel — ${label}` }),
        });
        await refresh();
        toast_('Claim submitted ✓', `${claim.claimId} is now in My claims.`);
        closeDrawer();
        nav('my-claims');
      } catch (err) {
        toast_('Claim failed', err.message, 'error');
      }
    };
  }
}

function openClaimDrawer(c) {
  // Find all bookings linked to this claim
  const allB = [...(S.bookings || []), ...(S.hotelBookings || [])];
  const linked = allB.filter(b => b.claimId === c.claimId);
  openDrawer(`
    <div class="drawer-content">
      <p class="eyebrow">EXPENSE REPORT</p>
      <h2>${esc(c.title)}</h2>
      <span class="badge badge-blue" style="margin-bottom:16px;display:inline-block">Submitted</span>
      <table class="ctable">
        <tr><td>Report ID</td><td>${esc(c.claimId)}</td></tr>
        <tr><td>Submitted</td><td>${fmt(c.submittedAt)}</td></tr>
        <tr><td>Bookings</td><td>${linked.length}</td></tr>
        <tr class="total-row"><td><strong>Total</strong></td><td><strong>${money(c.total)}</strong></td></tr>
      </table>
      ${linked.length ? `
        <div class="drawer-section">
          <p class="eyebrow">INCLUDED BOOKINGS</p>
          ${linked.map(b => `
            <div class="bm-mini">
              <span>${b.type === 'FLIGHT' ? '✈' : '🏨'}</span>
              <span>${b.type === 'FLIGHT' ? `${b.flight.from} → ${b.flight.to} · ${b.flight.airline} · ${b.travelDate}` : `${b.hotel.name} · ${b.checkin} – ${b.checkout}`}</span>
              <span>${money(b.totalPrice)}</span>
            </div>`).join('')}
        </div>` : ''}
      <div class="drawer-section">
        <p class="muted">To view full receipt details and policy checks, open the expense folder.</p>
        <button class="btn-secondary" style="margin-top:10px" id="drawerOpenFolder">Open expense folder →</button>
      </div>
    </div>`);

  document.getElementById('drawerOpenFolder').onclick = () => {
    window.open('http://localhost:3000', '_blank');
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
   PAGE REGISTRY + INIT
═══════════════════════════════════════════════════════════════════════════ */
const PAGES = {
  'dashboard':  pageDashboard,
  'new-claim':  pageNewClaim,
  'my-claims':  pageMyClaims,
  'book-flight':pageBookFlight,
  'book-hotel': pageBookHotel,
};

refresh()
  .catch(() => toast_('Service unavailable', 'Start the BFF (port 4000) and Concur stub (port 8001), then reload.', 'error'))
  .finally(() => nav('dashboard'));
