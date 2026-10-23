function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

// Convert UTC ISO timestamps to Device Standard Time
function formatDeviceTime(isoStr, includeSeconds = false) {
  if (!isoStr) return '—';
  try {
    const s = (isoStr.endsWith('Z') || isoStr.includes('+')) ? isoStr : isoStr + 'Z';
    const d = new Date(s);
    if (isNaN(d.getTime())) return isoStr;
    const pad = (n) => String(n).padStart(2, '0');
    const y = d.getFullYear();
    const m = pad(d.getMonth() + 1);
    const day = pad(d.getDate());
    const hh = pad(d.getHours());
    const mm = pad(d.getMinutes());
    if (includeSeconds) {
      const ss = pad(d.getSeconds());
      return `${y}-${m}-${day} ${hh}:${mm}:${ss}`;
    }
    return `${y}-${m}-${day} ${hh}:${mm}`;
  } catch (e) {
    return isoStr;
  }
}

function formatDeviceTimeOnly(isoStr) {
  if (!isoStr) return '';
  try {
    const s = (isoStr.endsWith('Z') || isoStr.includes('+')) ? isoStr : isoStr + 'Z';
    const d = new Date(s);
    if (isNaN(d.getTime())) return isoStr;
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch (e) {
    return isoStr;
  }
}

function updateDeviceTimes() {
  document.querySelectorAll('.device-time').forEach((el) => {
    const utc = el.getAttribute('data-utc');
    if (utc) {
      el.textContent = formatDeviceTime(utc, false);
    }
  });
  document.querySelectorAll('.device-time-sec').forEach((el) => {
    const utc = el.getAttribute('data-utc');
    if (utc) {
      el.textContent = formatDeviceTime(utc, true);
    }
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateDeviceTimes);
  } else {
    updateDeviceTimes();
  }
}
