/**
 * Alpha Decay Evidence Explorer & Observation Table Filtering
 * Verbatim modal inspector with XSS prevention & table search.
 */

function openEvidenceModal(index) {
  const data = window.INVESTIGATION_DATA || {};
  const evidenceList = data.evidence || [];

  if (index < 0 || index >= evidenceList.length) return;
  const ev = evidenceList[index];

  const modal = document.getElementById('evidence-modal');
  if (!modal) return;

  document.getElementById('modal-ev-id').innerText = ev.evidence_id || 'EV-UNKNOWN';
  document.getElementById('modal-ev-title').innerText = ev.source_title || 'Statutory Source';
  document.getElementById('modal-ev-publisher').innerText = ev.publisher || 'Exchange Filing';
  document.getElementById('modal-ev-period').innerText = ev.relevant_period || 'Trailing';
  document.getElementById('modal-ev-location').innerText = ev.source_location || 'Disclosures';
  document.getElementById('modal-ev-tier').innerText = `Tier ${ev.credibility_tier || 2}`;

  // Verbatim excerpt
  const excerptEl = document.getElementById('modal-ev-excerpt');
  if (excerptEl) {
    excerptEl.innerText = ev.supporting_excerpt || 'No excerpt available.';
  }

  // Core fact
  const factEl = document.getElementById('modal-ev-fact');
  if (factEl) {
    factEl.innerText = ev.extracted_fact || ev.source_title || '—';
  }

  // Source link
  const linkEl = document.getElementById('modal-ev-link');
  if (linkEl) {
    const rawUrl = ev.source_url || ev.url || '#';
    // Validate protocol to prevent javascript: URIs
    if (rawUrl.startsWith('http://') || rawUrl.startsWith('https://')) {
      linkEl.href = rawUrl;
      linkEl.style.display = 'inline-flex';
    } else {
      linkEl.href = '#';
      linkEl.style.display = 'none';
    }
  }

  modal.classList.add('open');
}

function closeEvidenceModal() {
  const modal = document.getElementById('evidence-modal');
  if (modal) {
    modal.classList.remove('open');
  }
}

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeEvidenceModal();
  }
});

// Tab E: Filter Observations Table
function filterObservationsTable() {
  const input = document.getElementById('filter-observations-input');
  if (!input) return;

  const query = input.value.toLowerCase().trim();
  const table = document.getElementById('observations-table');
  if (!table) return;

  const rows = table.querySelectorAll('tbody tr');
  rows.forEach(tr => {
    const text = tr.innerText.toLowerCase();
    tr.style.display = text.includes(query) ? '' : 'none';
  });
}
