/**
 * ALPHA-DECAY Real-Time Investigation Progress & Event Listener
 * Supports Server-Sent Events (SSE) with automatic polling fallback.
 */

(function() {
  const data = window.INVESTIGATION_DATA || {};
  const runId = data.runId;
  let status = data.status;

  if (!runId || (status !== 'QUEUED' && status !== 'RUNNING')) {
    return;
  }

  const STAGES_ORDER = [
    'data_ingestion',
    'financial_analytics',
    'anomaly_triage',
    'hypothesis_generation',
    'evidence_retrieval',
    'peer_analysis',
    'adversarial_assessment',
    'report_validation',
    'pdf_generation'
  ];

  let lastEventId = 0;
  let eventSource = null;
  let pollInterval = null;

  function updateStageVisuals(activeStage) {
    const activeIdx = STAGES_ORDER.indexOf(activeStage);
    const label = document.getElementById('active-stage-label');
    if (label) {
      label.innerText = `STAGE: ${activeStage.toUpperCase().replace('_', ' ')}`;
    }

    STAGES_ORDER.forEach((stage, idx) => {
      const card = document.getElementById(`stage-card-${stage}`);
      const desc = document.getElementById(`stage-desc-${stage}`);
      if (!card) return;

      if (idx < activeIdx) {
        card.className = 'pipeline-stage completed';
        if (desc) desc.innerText = 'Completed';
        const icon = card.querySelector('.stage-icon');
        if (icon) icon.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="12" height="12"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      } else if (idx === activeIdx) {
        card.className = 'pipeline-stage active';
        if (desc) desc.innerText = 'In progress...';
        const icon = card.querySelector('.stage-icon');
        if (icon) icon.innerHTML = '<span class="status-dot healthy" style="width: 8px; height: 8px;"></span>';
      } else {
        card.className = 'pipeline-stage pending';
        if (desc) desc.innerText = 'Pending';
      }
    });
  }

  function appendTimelineEvent(event) {
    if (!event || !event.message) return;
    const container = document.getElementById('timeline-events-container');
    if (!container) return;

    if (event.id) {
      lastEventId = Math.max(lastEventId, event.id);
    }

    const div = document.createElement('div');
    div.className = 'timeline-event';
    const timeStr = event.timestamp ? event.timestamp.substring(11, 19) : '';
    const sevClass = (event.severity || 'INFO').toLowerCase();

    div.innerHTML = `
      <div class="timeline-time">${timeStr}</div>
      <div class="timeline-msg">
        <span class="badge badge-queued" style="font-size: 10px; margin-right: 6px;">${event.stage || 'audit'}</span>
        <span>${escapeHtml(event.message)}</span>
      </div>
    `;

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    if (event.stage && STAGES_ORDER.includes(event.stage)) {
      updateStageVisuals(event.stage);
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#039;');
  }

  function handleRunCompletion(finalStatus) {
    const statusBadge = document.getElementById('run-status-badge');
    if (statusBadge) {
      statusBadge.className = `badge badge-${finalStatus.toLowerCase()}`;
      statusBadge.innerText = finalStatus;
    }

    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }

    // Refresh page after brief pause to load final compiled tabs
    setTimeout(() => {
      window.location.reload();
    }, 1200);
  }

  // 1. Establish SSE Connection
  function startSSE() {
    const statusText = document.getElementById('sse-connection-status');
    try {
      eventSource = new EventSource(`/api/investigations/${runId}/events/stream`);

      eventSource.onopen = function() {
        if (statusText) statusText.innerText = 'Live SSE connected';
      };

      eventSource.onmessage = function(e) {
        try {
          const ev = JSON.parse(e.data);
          appendTimelineEvent(ev);

          if (ev.stage === 'completed' || ev.stage === 'failed' || ev.stage === 'cancelled') {
            handleRunCompletion(ev.stage.toUpperCase());
          }
        } catch (err) {
          console.error('SSE parse error:', err);
        }
      };

      eventSource.onerror = function() {
        if (statusText) statusText.innerText = 'Reverting to polling fallback...';
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        startPolling();
      };
    } catch (err) {
      console.warn('SSE unsupported, starting polling:', err);
      startPolling();
    }
  }

  // 2. Polling Fallback Mechanism
  function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(() => {
      fetch(`/api/investigations/${runId}/events?since_id=${lastEventId}`)
        .then(res => res.json())
        .then(payload => {
          if (payload.events && payload.events.length > 0) {
            payload.events.forEach(appendTimelineEvent);
          }
          if (payload.status && payload.status !== 'QUEUED' && payload.status !== 'RUNNING') {
            handleRunCompletion(payload.status);
          }
        })
        .catch(err => console.error('Polling error:', err));
    }, 2000);
  }

  // Initial trigger
  startSSE();
})();

// Global Cancel Trigger
function cancelCurrentInvestigation(runId) {
  if (!confirm('Are you sure you want to cancel this financial investigation? Subsequent stages will be halted.')) {
    return;
  }

  const cancelBtn = document.getElementById('cancel-run-btn');
  if (cancelBtn) {
    cancelBtn.disabled = true;
    cancelBtn.innerText = 'Cancelling...';
  }

  fetch(`/api/investigations/${runId}/cancel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': getCsrfToken()
    },
    body: JSON.stringify({ csrf_token: getCsrfToken() })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showToast('Investigation cancellation requested.', 'warning');
      setTimeout(() => window.location.reload(), 1000);
    } else {
      showToast(data.error || 'Failed to cancel run.', 'danger');
      if (cancelBtn) cancelBtn.disabled = false;
    }
  })
  .catch(err => {
    showToast(`Error: ${err}`, 'danger');
    if (cancelBtn) cancelBtn.disabled = false;
  });
}
