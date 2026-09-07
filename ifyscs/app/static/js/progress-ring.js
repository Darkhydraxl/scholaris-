(function () {
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.js-progress-ring-circle').forEach((circle) => {
      const circumference = parseFloat(circle.dataset.circumference);
      const percent = parseFloat(circle.dataset.targetPercent);
      const offset = circumference - (circumference * Math.min(Math.max(percent, 0), 100)) / 100;
      // Let the layout settle (and the initial "full" dashoffset paint) before
      // transitioning, so the CSS transition on stroke-dashoffset is visible.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          circle.style.strokeDashoffset = String(offset);
        });
      });
    });
  });
})();
