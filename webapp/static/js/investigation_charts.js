/**
 * Alpha Decay Interactive Financial Analytics Chart Engine
 * Chart.js wrapper with dark terminal theme tokens, metric toggling,
 * zero false zeros, and tabular data view.
 */

window.forensicChart = null;
window.chartDataCache = null;
let currentMetricMode = 'sales_residual';

function initForensicChart() {
  const canvas = document.getElementById('forensic-interactive-chart');
  if (!canvas) return;

  const data = window.INVESTIGATION_DATA || {};
  const runId = data.runId;
  if (!runId) return;

  fetch(`/api/investigations/${runId}/metrics`)
    .then(res => res.json())
    .then(metricsPayload => {
      window.chartDataCache = metricsPayload;
      renderChart(metricsPayload, currentMetricMode);
      populateAnalyticsTable(metricsPayload);
    })
    .catch(err => {
      console.error('Failed to load metrics series for chart:', err);
    });
}

function renderChart(payload, mode) {
  const canvas = document.getElementById('forensic-interactive-chart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const quarters = payload.quarters || [];
  const series = payload.series || {};

  if (window.forensicChart) {
    window.forensicChart.destroy();
  }

  let datasets = [];
  let yAxisLabel = 'Growth Rate (%)';

  if (mode === 'sales_residual') {
    yAxisLabel = 'YoY Growth Rate (%)';
    datasets = [
      {
        label: 'Reported Net Sales Growth YoY (%)',
        data: series.sales_growth_yoy || [],
        borderColor: '#58A6FF',
        backgroundColor: 'rgba(88, 166, 255, 0.1)',
        borderWidth: 2,
        pointBackgroundColor: '#58A6FF',
        pointRadius: 4,
        pointHoverRadius: 6,
        spanGaps: false,
        tension: 0.1
      },
      {
        label: 'Expense Residual Heuristic (%)',
        data: series.expense_adjusted_residual || [],
        borderColor: '#F5C84C',
        backgroundColor: 'rgba(245, 200, 76, 0.08)',
        borderWidth: 2,
        borderDash: [5, 4],
        pointBackgroundColor: '#F5C84C',
        pointRadius: 4,
        pointHoverRadius: 6,
        spanGaps: false,
        tension: 0.1
      }
    ];
  } else if (mode === 'debtor_days') {
    yAxisLabel = 'Debtor Days (d)';
    datasets = [
      {
        label: 'Statutory Debtor Days (Turnover Velocity)',
        data: series.debtor_days || [],
        borderColor: '#39D98A',
        backgroundColor: 'rgba(57, 217, 138, 0.1)',
        borderWidth: 2.2,
        pointBackgroundColor: '#39D98A',
        pointRadius: 5,
        pointHoverRadius: 7,
        spanGaps: false,
        tension: 0.1
      }
    ];
  }

  window.forensicChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: quarters,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          labels: {
            color: '#F3F6FA',
            font: {
              family: 'inherit',
              size: 11.5,
              weight: '500'
            },
            boxWidth: 14,
            padding: 16
          }
        },
        tooltip: {
          backgroundColor: '#0D1117',
          titleColor: '#F3F6FA',
          bodyColor: '#9AA8B7',
          borderColor: '#273241',
          borderWidth: 1,
          padding: 12,
          boxPadding: 6,
          usePointStyle: true,
          callbacks: {
            label: function(context) {
              const label = context.dataset.label || '';
              const val = context.parsed.y;
              if (val === null || val === undefined || isNaN(val)) {
                return `${label}: N/A (Missing disclosure)`;
              }
              const unit = mode === 'debtor_days' ? 'd' : '%';
              return `${label}: ${val >= 0 ? '+' : ''}${val}${unit}`;
            },
            footer: function() {
              if (mode === 'sales_residual') {
                return 'Note: Expense residual is a screening heuristic proxy, not reported volume.';
              }
              return 'Source: Audited Balance Sheet & Ratios';
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(39, 50, 65, 0.6)',
            borderColor: '#273241'
          },
          ticks: {
            color: '#9AA8B7',
            font: {
              family: 'monospace',
              size: 10.5
            }
          }
        },
        y: {
          title: {
            display: true,
            text: yAxisLabel,
            color: '#9AA8B7',
            font: {
              size: 11,
              weight: '600'
            }
          },
          grid: {
            color: 'rgba(39, 50, 65, 0.6)',
            borderColor: '#273241'
          },
          ticks: {
            color: '#9AA8B7',
            font: {
              family: 'monospace',
              size: 10.5
            }
          }
        }
      }
    }
  });
}

function selectChartMetric(mode) {
  currentMetricMode = mode;
  document.getElementById('metric-btn-sales').classList.toggle('active', mode === 'sales_residual');
  document.getElementById('metric-btn-debtor').classList.toggle('active', mode === 'debtor_days');

  if (window.chartDataCache) {
    renderChart(window.chartDataCache, mode);
  }
}

function toggleAnalyticsTableView() {
  const chartWrapper = document.getElementById('chart-wrapper');
  const tableView = document.getElementById('analytics-table-view');
  const btn = document.getElementById('toggle-table-btn');

  if (tableView.style.display === 'none') {
    tableView.style.display = 'block';
    btn.classList.add('active');
    btn.innerText = 'Hide Table View';
  } else {
    tableView.style.display = 'none';
    btn.classList.remove('active');
    btn.innerText = 'Data Table View';
  }
}

function populateAnalyticsTable(payload) {
  const tbody = document.getElementById('analytics-table-body');
  if (!tbody) return;

  tbody.innerHTML = '';
  const quarters = payload.quarters || [];
  const series = payload.series || {};

  quarters.forEach((q, idx) => {
    const s = series.sales_growth_yoy ? series.sales_growth_yoy[idx] : null;
    const r = series.expense_adjusted_residual ? series.expense_adjusted_residual[idx] : null;
    const d = series.debtor_days ? series.debtor_days[idx] : null;

    let spread = 'N/A';
    if (s !== null && r !== null && s !== undefined && r !== undefined) {
      spread = `${(s - r).toFixed(2)}%`;
    }

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><code>${q}</code></td>
      <td style="font-family: monospace; font-weight: 600; color: #58A6FF;">${s !== null && s !== undefined ? s + '%' : '<span style="color: #F5C84C">N/A</span>'}</td>
      <td style="font-family: monospace; font-weight: 600; color: #F5C84C;">${r !== null && r !== undefined ? r + '%' : '<span style="color: #F5C84C">N/A</span>'}</td>
      <td style="font-family: monospace; color: var(--text-secondary);">${spread}</td>
      <td style="font-family: monospace; font-weight: 600; color: #39D98A;">${d !== null && d !== undefined ? d + 'd' : '<span style="color: #F5C84C">N/A</span>'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  initForensicChart();
});
