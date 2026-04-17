// ============================================================
// dashboard_module3.js  – Consolidated JS for all M3 dashboards
// Depends on: window.M3_CONFIG being set by the template
// ============================================================

const M3 = window.M3_CONFIG || {};
const BASE = M3.base_url || '/module3';  // e.g. /module3

// ── Toast ────────────────────────────────────────────────────
function showToast(message, type = 'success') {
    let toast = document.getElementById('m3-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'm3-toast';
        Object.assign(toast.style, {
            position: 'fixed', right: '24px', bottom: '24px',
            zIndex: 9999, maxWidth: '360px', padding: '14px 20px',
            borderRadius: '14px', fontWeight: '700', fontSize: '0.93rem',
            letterSpacing: '0.2px', boxShadow: '0 12px 32px rgba(15,23,42,.25)',
            opacity: '0', transform: 'translateY(12px)',
            transition: 'opacity .25s ease, transform .25s ease', color: '#fff',
            pointerEvents: 'auto', wordWrap: 'break-word',
        });
        document.body.appendChild(toast);
    }
    const colors = {
        success: 'linear-gradient(135deg,#16a34a 0%,#22c55e 100%)',
        error:   'linear-gradient(135deg,#dc2626 0%,#ef4444 100%)',
        warning: 'linear-gradient(135deg,#d97706 0%,#f59e0b 100%)',
        info:    'linear-gradient(135deg,#2563eb 0%,#3b82f6 100%)',
    };
    toast.style.background = colors[type] || colors.success;
    toast.textContent = message;
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    });
    const dur = { success: 3500, error: 4500, warning: 4000, info: 3200 }[type] || 3500;
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px)';
    }, dur);
}

// ── Summary card updater ─────────────────────────────────────
function updateSummaryCards(data) {
    const stats = {
        total:      data.length,
        pending:    data.filter(d => d.status === 'Pending').length,
        inprogress: data.filter(d => d.status === 'In Progress').length,
        delayed:    data.filter(d => d.status === 'Delayed').length,
        overdue:    data.filter(d => d.is_overdue).length,
        completed:  data.filter(d => d.status === 'Completed' && !d.closed).length,
        closed:     data.filter(d => d.closed).length,
    };
    const values = [stats.total, stats.pending, stats.inprogress, stats.delayed, stats.overdue, stats.completed, stats.closed];
    document.querySelectorAll('.m3-summary-card .m3-value').forEach((el, i) => {
        el.textContent = values[i] != null ? values[i] : '0';
    });
}

// ── Table population ─────────────────────────────────────────
function populateTable(data) {
    const tbody = document.getElementById('m3-defect-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!data.length) {
        const cols = window.M3_TABLE_COLS || 6;
        tbody.innerHTML = `<tr><td colspan="${cols}" style="text-align:center;padding:2.5rem;color:#64748b;">No defects match the selected filters.</td></tr>`;
        updateSummaryCards([]);
        return;
    }
    data.forEach(d => {
        const statusClass = d.closed
            ? 'badge-closed'
            : d.display_status === 'Completed' ? 'badge-completed'
            : d.is_overdue ? 'badge-overdue'
            : 'badge-pending';
        const row = document.createElement('tr');
        row.className = 'm3-row';
        row.innerHTML = buildRow(d, statusClass);
        tbody.appendChild(row);
    });
    updateSummaryCards(data);
}

// Overridable by each dashboard template
window.buildRow = window.buildRow || function(d, statusClass) {
    return `
        <td class="m3-td">#${d.id}</td>
        <td class="m3-td">${d.unit || '-'}</td>
        <td class="m3-td">${d.desc || '-'}</td>
        <td class="m3-td"><span class="m3-badge ${statusClass}">${d.display_status}</span></td>
        <td class="m3-td">${d.remarks || '-'}</td>
        <td class="m3-td">-</td>`;
};

// ── Filters ──────────────────────────────────────────────────
function applyFilters() {
    const statusFilter = (document.getElementById('m3-filter-status') || {}).value || '';
    const unitFilter   = (document.getElementById('m3-filter-unit')   || {}).value || '';
    const filtered = (window.allDefects || []).filter(d => {
        const sm = !statusFilter || d.display_status === statusFilter;
        const um = !unitFilter   || d.unit === unitFilter;
        return sm && um;
    });
    populateTable(filtered);
}

function resetFilters() {
    const s = document.getElementById('m3-filter-status');
    const u = document.getElementById('m3-filter-unit');
    if (s) s.value = '';
    if (u) u.value = '';
    populateTable(window.allDefects || []);
}

// ── Report generation ────────────────────────────────────────
function invalidateReportExport() {
    const btn = document.getElementById('m3-export-btn');
    const inp = document.getElementById('m3-pdf-ai-report');
    if (btn) btn.disabled = true;
    if (inp) inp.value = '';
}

function generateReport() {
    const lang = (document.getElementById('m3-language-select') || {}).value;
    if (!lang) { showToast('Please select a language.', 'warning'); return; }

    const claimantSel = document.getElementById('m3-claimant-select');
    const claimantUserId = claimantSel ? claimantSel.value : '';

    invalidateReportExport();
    const pdfLang = document.getElementById('m3-pdf-language');
    const pdfCid  = document.getElementById('m3-pdf-claimant-user-id');
    if (pdfLang) pdfLang.value = lang;
    if (pdfCid)  pdfCid.value  = claimantUserId;

    const output = document.getElementById('m3-report-output');
    const preview = document.getElementById('m3-report-preview');
    if (output)  output.style.display = 'block';
    if (preview) preview.textContent = 'Generating report…';

    fetch(`${BASE}/generate_ai_report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: M3.role, language: lang, claimant_user_id: claimantUserId }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            showToast(data.error, 'error');
            if (preview) preview.textContent = Array.isArray(data.details)
                ? 'Missing data:\n' + data.details.map((x, i) => `${i+1}. ${x}`).join('\n')
                : (data.details || 'Unable to generate report.');
            return;
        }
        if (!data.report || !data.report.trim()) {
            showToast('Report is empty. Add defect data first.', 'warning');
            if (preview) preview.textContent = 'No report data available.';
            return;
        }
        if (preview) preview.textContent = data.report;
        const pdfRep = document.getElementById('m3-pdf-ai-report');
        if (pdfRep) pdfRep.value = data.report;
        const exp = document.getElementById('m3-export-btn');
        if (exp) exp.disabled = false;
        showToast('✓ Report generated!', 'success');
    })
    .catch(() => {
        showToast('Network error – could not generate report.', 'error');
        if (preview) preview.textContent = 'Request failed.';
    });
}

// ── Save claim details (Homeowner) ───────────────────────────
function saveClaimDetails() {
    const g = id => (document.getElementById(id) || {}).value || '';
    const payload = {
        court_location:   g('m3-court-location'),
        state_name:       g('m3-state-name'),
        item_service:     g('m3-item-service'),
        transaction_date: g('m3-transaction-date'),
        claim_amount:     g('m3-claim-amount'),
    };
    fetch(`${BASE}/save_homeowner_claim_details`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    })
    .then(r => r.json())
    .then(d => showToast(d.success ? 'Claim details saved.' : (d.error || 'Save failed.'), d.success ? 'success' : 'error'))
    .catch(() => showToast('Save failed.', 'error'));
}

// ── Court location helper ────────────────────────────────────
window.STATE_COURT_MAP = window.STATE_COURT_MAP || {};

function populateCourtLocations(stateName, selectedCourt) {
    const sel = document.getElementById('m3-court-location');
    if (!sel) return;
    const entry = STATE_COURT_MAP[stateName] || {};
    const branches = entry.tribunal_branches || [];
    const general  = entry.general_locations || [];
    sel.innerHTML = '<option value="">Select court location</option>';
    if (!stateName) { sel.disabled = true; return; }
    sel.disabled = false;
    if (branches.length) {
        const g = document.createElement('optgroup'); g.label = 'Tribunal Branches';
        branches.forEach(l => { const o = new Option(l, l); g.appendChild(o); });
        sel.appendChild(g);
    }
    if (general.length) {
        const g = document.createElement('optgroup'); g.label = 'General Court Locations';
        general.filter(l => !branches.includes(l)).forEach(l => { const o = new Option(l, l); g.appendChild(o); });
        if (g.children.length) sel.appendChild(g);
    }
    if (selectedCourt) sel.value = selectedCourt;
}

function syncCourtLocations() {
    const s = document.getElementById('m3-state-name');
    const c = document.getElementById('m3-court-location');
    populateCourtLocations(s ? s.value : '', c ? c.value : '');
}

// ── Status update modal (Developer) ─────────────────────────
let _currentUpdateId = null;

function openUpdateModal(id) {
    const d = (window.allDefects || []).find(x => x.id === id);
    if (d && d.closed) { showToast('Case is already closed.', 'info'); return; }
    _currentUpdateId = id;
    const el = document.getElementById('m3-modal-defect-id');
    if (el) el.textContent = id;
    const overlay = document.getElementById('m3-update-modal');
    if (overlay) overlay.classList.add('m3-modal-show');
    const ss = document.getElementById('m3-new-status-select');
    if (ss) { ss.value = 'In Progress'; _onStatusSelectChange(); }
}
function closeUpdateModal() {
    const overlay = document.getElementById('m3-update-modal');
    if (overlay) overlay.classList.remove('m3-modal-show');
}
function _onStatusSelectChange() {
    const ss  = document.getElementById('m3-new-status-select');
    const cdw = document.getElementById('m3-completion-date-wrapper');
    if (cdw) cdw.style.display = ss && ss.value === 'Completed' ? 'block' : 'none';
}
function confirmUpdate() {
    const id  = _currentUpdateId;
    const ss  = document.getElementById('m3-new-status-select');
    const cdi = document.getElementById('m3-completion-date');
    const status = ss ? ss.value : '';
    const completed_date = cdi ? cdi.value : '';
    if (status === 'Completed' && !completed_date) {
        showToast('Please select a completion date.', 'warning'); return;
    }
    if (status === 'Completed' && completed_date) {
        if (new Date(`${completed_date}T00:00:00`) > new Date()) {
            showToast('Completion date cannot be in the future.', 'warning'); return;
        }
    }
    fetch(`${BASE}/update_status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status, completed_date }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            showToast('Status updated.', 'success');
            closeUpdateModal();
            invalidateReportExport();
            setTimeout(() => window.location.reload(), 350);
        } else {
            showToast(data.message || 'Update failed.', 'error');
        }
    })
    .catch(() => showToast('Update failed.', 'error'));
}

// ── Remark modal (Homeowner) ─────────────────────────────────
let _currentRemarkId = null;

function openRemarkModal(id) {
    _currentRemarkId = id;
    const el = document.getElementById('m3-modal-remark-id');
    if (el) el.textContent = id;
    const d = (window.allDefects || []).find(x => x.id === id);
    const ta = document.getElementById('m3-remark-textarea');
    if (ta) ta.value = d ? (d.remarks || '') : '';
    const ov = document.getElementById('m3-remark-modal');
    if (ov) ov.classList.add('m3-modal-show');
}
function closeRemarkModal() {
    const ov = document.getElementById('m3-remark-modal');
    if (ov) ov.classList.remove('m3-modal-show');
}
function saveRemark() {
    const ta = document.getElementById('m3-remark-textarea');
    const remark = ta ? ta.value.trim() : '';
    if (!remark) { showToast('Please enter a remark.', 'warning'); return; }
    fetch(`${BASE}/add_remark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: _currentRemarkId, remark, role: 'Homeowner' }),
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            const d = (window.allDefects || []).find(x => x.id === _currentRemarkId);
            if (d) d.remarks = remark;
            applyFilters();
            showToast('Remark saved.', 'success');
            closeRemarkModal();
        } else {
            showToast(data.error || 'Save failed.', 'error');
        }
    })
    .catch(() => showToast('Save failed.', 'error'));
}

// ── Evidence upload (Homeowner) ──────────────────────────────
function showUploadHint(defectId) {
    showToast('Accepted: JPG, JPEG, PNG, TIF, TIFF (Max 10MB)', 'info');
    setTimeout(() => {
        const fi = document.getElementById(`m3-file-${defectId}`);
        if (fi) fi.click();
    }, 300);
}
function uploadEvidence(defectId) {
    const fi = document.getElementById(`m3-file-${defectId}`);
    const file = fi && fi.files[0];
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['jpg','jpeg','png','tif','tiff'].includes(ext)) {
        showToast('Invalid file type.', 'error'); fi.value = ''; return;
    }
    if (file.size > 10 * 1024 * 1024) {
        showToast('File exceeds 10 MB limit.', 'error'); fi.value = ''; return;
    }
    const fd = new FormData();
    fd.append('file', file);
    fd.append('defect_id', defectId);
    fetch(`${BASE}/upload_evidence`, { method: 'POST', body: fd })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const d = (window.allDefects || []).find(x => x.id === Number(defectId));
                if (d) {
                    d.evidence_uploaded = true;
                    d.evidence_filename  = data.filename || d.evidence_filename || '';
                    d.evidence_uploaded_at = data.uploaded_at || d.evidence_uploaded_at || '';
                }
                applyFilters();
                showToast('✓ Evidence uploaded!', 'success');
                fi.value = '';
            } else {
                showToast(data.error || 'Upload failed.', 'error');
            }
        })
        .catch(() => showToast('Upload failed.', 'error'));
}

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    populateTable(window.allDefects || []);

    const ss = document.getElementById('m3-new-status-select');
    if (ss) ss.addEventListener('change', _onStatusSelectChange);

    // Court locations – initialise with server-provided defaults
    if (M3.initial_state_name !== undefined) {
        populateCourtLocations(M3.initial_state_name, M3.initial_court_location || '');
    }
});
