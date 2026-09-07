(function () {
  function getCsrfToken() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.content : '';
  }

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('themeToggleBtn');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const html = document.documentElement;
      const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      // Notify canvas-based charts (Chart.js, progress rings) so they can redraw
      // with the new CSS variable values without a full page reload.
      window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
      fetch('/theme/toggle', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
    });
  });
})();
