(function () {
  const MAX_TILT_DEG = 6;

  function attachTilt(card) {
    let frame = null;

    function onMouseMove(e) {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const px = (x / rect.width) - 0.5;
        const py = (y / rect.height) - 0.5;
        const rotateY = px * MAX_TILT_DEG * 2;
        const rotateX = -py * MAX_TILT_DEG * 2;
        card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(0)`;
        frame = null;
      });
    }

    function onMouseLeave() {
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0)';
    }

    card.addEventListener('mousemove', onMouseMove);
    card.addEventListener('mouseleave', onMouseLeave);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.card-tilt').forEach(attachTilt);
  });
})();
