(function () {
  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function animateCountUp(el) {
    const target = parseFloat(el.dataset.target || '0');
    const suffix = el.dataset.suffix || '';
    const duration = 1100;
    const start = performance.now();

    function frame(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = easeOutCubic(progress);
      const value = Math.round(target * eased);
      el.textContent = `${value}${suffix}`;
      if (progress < 1) requestAnimationFrame(frame);
      else el.textContent = `${target}${suffix}`;
    }
    requestAnimationFrame(frame);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.js-count-up').forEach(animateCountUp);
  });
})();
