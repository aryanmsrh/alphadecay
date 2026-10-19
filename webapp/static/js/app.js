/**
 * Alpha Decay Common Frontend Utilities
 * CSRF token management, toast notifications, tab switching
 */

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `alert-banner alert-${type}`;
  toast.style.boxShadow = '0 8px 24px rgba(0,0,0,0.5)';
  toast.style.margin = '0';
  toast.style.padding = '10px 16px';
  toast.style.fontSize = '12.5px';
  toast.style.maxWidth = '360px';
  toast.style.animation = 'fadeIn 0.2s ease';

  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function switchTab(tabId) {
  // Update tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  const targetBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => {
    return b.getAttribute('onclick') && b.getAttribute('onclick').includes(tabId);
  });
  if (targetBtn) targetBtn.classList.add('active');

  // Update tab content panes
  document.querySelectorAll('.tab-content').forEach(pane => pane.classList.remove('active'));
  const targetPane = document.getElementById(tabId);
  if (targetPane) targetPane.classList.add('active');

  // Trigger chart resize if switching to analytics
  if (tabId === 'tab-analytics' && window.forensicChart) {
    setTimeout(() => window.forensicChart.resize(), 50);
  }
}
