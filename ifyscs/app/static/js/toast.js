(function () {
  const stack = document.getElementById('toastStack');

  function showToast(message, category) {
    if (!stack) return;
    category = category || 'info';
    const typeClass = category === 'error' ? 'toast-error' : category === 'success' ? 'toast-success' : '';
    const toast = document.createElement('div');
    toast.className = `toast ${typeClass}`;
    toast.innerHTML = `
      <div class="toast-title">${category === 'error' ? 'Error' : category === 'success' ? 'Success' : 'Notice'}</div>
      <div class="toast-msg">${message}</div>
      <div class="toast-progress"></div>
    `;
    stack.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));

    const remove = () => {
      toast.classList.remove('show');
      toast.classList.add('hide');
      setTimeout(() => toast.remove(), 240);
    };
    const timer = setTimeout(remove, 4000);
    toast.addEventListener('mouseenter', () => clearTimeout(timer));
  }

  window.Scholaris = window.Scholaris || {};
  window.Scholaris.showToast = showToast;

  document.addEventListener('DOMContentLoaded', () => {
    const flashEl = document.getElementById('flashMessages');
    if (flashEl) {
      try {
        const flashes = JSON.parse(flashEl.dataset.flashes || '[]');
        flashes.forEach(([category, message]) => showToast(message, category));
      } catch (e) { /* ignore malformed flash payload */ }
    }
  });
})();
