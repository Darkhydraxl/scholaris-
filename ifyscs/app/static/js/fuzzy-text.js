/**
 * FuzzyText — vanilla JS port of the React Bits FuzzyText component.
 * Usage: FuzzyText(canvasElement, "text", { ...options })
 * Returns { destroy() } for cleanup.
 */
function FuzzyText(canvas, text, options) {
  var o = Object.assign({
    fontSize: 'clamp(3rem, 16vw, 11rem)',
    fontWeight: 900,
    fontFamily: 'inherit',
    color: '#fff',
    enableHover: true,
    baseIntensity: 0.18,
    hoverIntensity: 0.5,
    fuzzRange: 30,
    fps: 60,
    direction: 'horizontal',
    transitionDuration: 0,
    clickEffect: false,
    glitchMode: false,
    glitchInterval: 2000,
    glitchDuration: 200,
    gradient: null,
    letterSpacing: 0,
  }, options || {});

  var animId, cancelled = false, glitchTid, glitchEndTid, clickTid;

  function init() {
    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    var family = o.fontFamily === 'inherit'
      ? (window.getComputedStyle(canvas).fontFamily || 'sans-serif')
      : o.fontFamily;
    var sizeStr = typeof o.fontSize === 'number' ? o.fontSize + 'px' : o.fontSize;

    var ready = document.fonts
      ? document.fonts.load(o.fontWeight + ' ' + sizeStr + ' ' + family).catch(function () { return document.fonts.ready; })
      : Promise.resolve();

    ready.then(function () {
      if (cancelled) return;

      /* Resolve numeric font size */
      var numSize;
      if (typeof o.fontSize === 'number') {
        numSize = o.fontSize;
      } else {
        var tmp = document.createElement('span');
        tmp.style.fontSize = o.fontSize;
        document.body.appendChild(tmp);
        numSize = parseFloat(window.getComputedStyle(tmp).fontSize);
        document.body.removeChild(tmp);
      }

      /* Measure text on an offscreen canvas */
      var off = document.createElement('canvas');
      var octx = off.getContext('2d');
      octx.font = o.fontWeight + ' ' + sizeStr + ' ' + family;
      octx.textBaseline = 'alphabetic';

      var totalW = 0;
      if (o.letterSpacing) {
        for (var c of text) totalW += octx.measureText(c).width + o.letterSpacing;
        totalW -= o.letterSpacing;
      } else {
        totalW = octx.measureText(text).width;
      }

      var m = octx.measureText(text);
      var aLeft    = m.actualBoundingBoxLeft   != null ? m.actualBoundingBoxLeft   : 0;
      var aRight   = o.letterSpacing ? totalW  : (m.actualBoundingBoxRight  != null ? m.actualBoundingBoxRight  : m.width);
      var aAscent  = m.actualBoundingBoxAscent  != null ? m.actualBoundingBoxAscent  : numSize;
      var aDescent = m.actualBoundingBoxDescent != null ? m.actualBoundingBoxDescent : numSize * 0.2;

      var bW = Math.ceil(o.letterSpacing ? totalW : aLeft + aRight);
      var bH = Math.ceil(aAscent + aDescent);

      var xBuf = 10;
      var offW = bW + xBuf;
      off.width  = offW;
      off.height = bH;

      octx.font = o.fontWeight + ' ' + sizeStr + ' ' + family;
      octx.textBaseline = 'alphabetic';

      if (o.gradient && o.gradient.length >= 2) {
        var grad = octx.createLinearGradient(0, 0, offW, 0);
        o.gradient.forEach(function (col, i) {
          grad.addColorStop(i / (o.gradient.length - 1), col);
        });
        octx.fillStyle = grad;
      } else {
        octx.fillStyle = o.color;
      }

      if (o.letterSpacing) {
        var xp = xBuf / 2;
        for (var ch of text) {
          octx.fillText(ch, xp, aAscent);
          xp += octx.measureText(ch).width + o.letterSpacing;
        }
      } else {
        octx.fillText(text, xBuf / 2 - aLeft, aAscent);
      }

      var hMar = o.fuzzRange + 20;
      canvas.width  = offW + hMar * 2;
      canvas.height = bH;
      ctx.translate(hMar, 0);

      var iLeft   = hMar + xBuf / 2;
      var iTop    = 0;
      var iRight  = iLeft + bW;
      var iBottom = bH;

      var hovering = false, clicking = false, glitching = false;
      var cur = o.baseIntensity, tgt = o.baseIntensity;
      var lastT = 0, frameDur = 1000 / o.fps;

      function glitchLoop() {
        if (!o.glitchMode || cancelled) return;
        glitchTid = setTimeout(function () {
          if (cancelled) return;
          glitching = true;
          glitchEndTid = setTimeout(function () { glitching = false; glitchLoop(); }, o.glitchDuration);
        }, o.glitchInterval);
      }
      if (o.glitchMode) glitchLoop();

      function draw(ts) {
        if (cancelled) return;
        if (ts - lastT < frameDur) { animId = requestAnimationFrame(draw); return; }
        lastT = ts;

        ctx.clearRect(-o.fuzzRange - 20, -o.fuzzRange - 10,
          offW + 2 * (o.fuzzRange + 20), bH + 2 * (o.fuzzRange + 10));

        tgt = clicking ? 1 : glitching ? 1 : hovering ? o.hoverIntensity : o.baseIntensity;

        if (o.transitionDuration > 0) {
          var step = 1 / (o.transitionDuration / frameDur);
          cur = cur < tgt ? Math.min(cur + step, tgt) : Math.max(cur - step, tgt);
        } else {
          cur = tgt;
        }

        if (o.direction === 'vertical') {
          for (var i = 0; i < offW; i++) {
            var dy = Math.floor(cur * (Math.random() - 0.5) * o.fuzzRange);
            ctx.drawImage(off, i, 0, 1, bH, i, dy, 1, bH);
          }
        } else {
          for (var j = 0; j < bH; j++) {
            var dx = Math.floor(cur * (Math.random() - 0.5) * o.fuzzRange);
            ctx.drawImage(off, 0, j, offW, 1, dx, j, offW, 1);
          }
        }

        animId = requestAnimationFrame(draw);
      }
      animId = requestAnimationFrame(draw);

      function inside(x, y) { return x >= iLeft && x <= iRight && y >= iTop && y <= iBottom; }

      function onMove(e) {
        var r = canvas.getBoundingClientRect();
        hovering = inside(e.clientX - r.left, e.clientY - r.top);
      }
      function onLeave() { hovering = false; }
      function onClick() {
        if (!o.clickEffect) return;
        clicking = true;
        clearTimeout(clickTid);
        clickTid = setTimeout(function () { clicking = false; }, 150);
      }
      function onTouch(e) {
        e.preventDefault();
        var r = canvas.getBoundingClientRect(), t = e.touches[0];
        hovering = inside(t.clientX - r.left, t.clientY - r.top);
      }
      function onTouchEnd() { hovering = false; }

      if (o.enableHover) {
        canvas.addEventListener('mousemove', onMove);
        canvas.addEventListener('mouseleave', onLeave);
        canvas.addEventListener('touchmove', onTouch, { passive: false });
        canvas.addEventListener('touchend', onTouchEnd);
      }
      if (o.clickEffect) canvas.addEventListener('click', onClick);
    });
  }

  init();

  return {
    destroy: function () {
      cancelled = true;
      cancelAnimationFrame(animId);
      clearTimeout(glitchTid);
      clearTimeout(glitchEndTid);
      clearTimeout(clickTid);
    }
  };
}
