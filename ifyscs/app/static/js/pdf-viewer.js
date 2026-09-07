(function () {
  if (!window.ScholarisPDF || typeof pdfjsLib === 'undefined') return;
  const config = window.ScholarisPDF;
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  let pdfDoc       = null;
  let currentPage  = 1;
  let currentScale = 1;   /* CSS scale — what annotations.js uses for positioning */
  let rendering    = false;
  let pendingPage  = null;  /* queued page request while rendering is in progress */

  const canvas        = document.getElementById('pdfCanvas');
  if (!canvas) return;
  const ctx           = canvas.getContext('2d');
  const textLayerDiv  = document.getElementById('pdfTextLayer');
  const pageContainer = document.getElementById('pdfPageContainer');
  const viewerWrap    = document.getElementById('pdfViewerWrap');
  const pageNumEl     = document.getElementById('pdfPageNum');
  const pageCountEl   = document.getElementById('pdfPageCount');

  /* Scale the page so it fits inside viewerWrap (both axes). */
  function calcScale(page) {
    if (!viewerWrap) return 1.5;
    const vp1    = page.getViewport({ scale: 1 });
    const availW = viewerWrap.clientWidth  - 36;   /* subtract 18px padding × 2 */
    const availH = viewerWrap.clientHeight - 36;
    const scaleW = availW / vp1.width;
    const scaleH = availH > 40 ? availH / vp1.height : scaleW;
    return Math.min(Math.max(Math.min(scaleW, scaleH), 0.3), 4);
  }

  async function renderPage(num) {
    if (!pdfDoc) return;
    if (rendering) { pendingPage = num; return; }   /* queue, don't drop */
    rendering = true;
    pendingPage = null;
    try {
      const page      = await pdfDoc.getPage(num);
      const cssScale  = calcScale(page);           /* scale in CSS pixels */
      const dpr       = window.devicePixelRatio || 1;
      /* Render at cssScale×dpr so the canvas is crisp on high-DPI screens. */
      const viewport  = page.getViewport({ scale: cssScale * dpr });

      /* Physical canvas size = CSS size × dpr */
      canvas.width         = viewport.width;
      canvas.height        = viewport.height;
      /* CSS displayed size = what the user sees */
      canvas.style.width   = (viewport.width  / dpr) + 'px';
      canvas.style.height  = (viewport.height / dpr) + 'px';

      /* Size the container to CSS pixels (not physical) so overlays line up */
      const cssW = viewport.width  / dpr;
      const cssH = viewport.height / dpr;
      if (pageContainer) {
        pageContainer.style.width  = cssW + 'px';
        pageContainer.style.height = cssH + 'px';
      }
      if (textLayerDiv) {
        textLayerDiv.innerHTML = '';
        textLayerDiv.style.width  = cssW + 'px';
        textLayerDiv.style.height = cssH + 'px';
        /* text layer needs the CSS viewport (not the physical one) */
        textLayerDiv.style.setProperty('--scale-factor', String(cssScale));
      }

      await page.render({ canvasContext: ctx, viewport }).promise;

      /* Text layer (best-effort) */
      try {
        if (textLayerDiv && typeof pdfjsLib.renderTextLayer === 'function') {
          const textContent = await page.getTextContent();
          /* renderTextLayer expects a viewport at the CSS scale, not physical */
          const cssViewport = page.getViewport({ scale: cssScale });
          const task = pdfjsLib.renderTextLayer({
            textContentSource: textContent,
            container: textLayerDiv,
            viewport: cssViewport,
            textDivs: [],
          });
          if (task && task.promise) await task.promise;
        }
      } catch (_) { /* text layer optional */ }

      currentPage  = num;
      currentScale = cssScale;
      if (pageNumEl) pageNumEl.textContent = String(num);

      document.dispatchEvent(new CustomEvent('pdf:rendered', {
        detail: { pageNumber: num, viewport, scale: cssScale },
      }));
    } finally {
      rendering = false;
      if (pendingPage !== null) {
        const next = pendingPage;
        pendingPage = null;
        renderPage(next);   /* render the queued page now */
      }
    }
  }

  /* Debounced resize → recalculate fit scale.
     Skip height-only changes (virtual keyboard open/close on Android) so
     the annotation popover isn't destroyed mid-comment. */
  let resizeTimer  = null;
  let lastResizeW  = window.innerWidth;
  window.addEventListener('resize', function () {
    const w = window.innerWidth;
    if (Math.abs(w - lastResizeW) < 10) return;   /* width unchanged → keyboard, not layout */
    lastResizeW = w;
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () { renderPage(currentPage); }, 200);
  });

  /* Public API */
  config.getCurrentPage = () => currentPage;
  config.getScale       = () => currentScale;
  config.goToPage       = (num) => {
    if (pdfDoc && num >= 1 && num <= pdfDoc.numPages) renderPage(num);
  };

  async function init() {
    try {
      pdfDoc = await pdfjsLib.getDocument(config.url).promise;
    } catch (e) {
      console.error('PDF load error:', e);
      return;
    }
    if (pageCountEl) pageCountEl.textContent = String(pdfDoc.numPages);

    const prevBtn = document.getElementById('pdfPrevPage');
    const nextBtn = document.getElementById('pdfNextPage');
    if (prevBtn) prevBtn.addEventListener('click', () => { if (currentPage > 1) renderPage(currentPage - 1); });
    if (nextBtn) nextBtn.addEventListener('click', () => { if (currentPage < pdfDoc.numPages) renderPage(currentPage + 1); });

    await renderPage(1);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
