(function () {
  if (!window.ScholarisPDF) return;
  var cfg          = window.ScholarisPDF;
  var isSupervisor = cfg.mode === 'supervisor';

  var pageContainer = document.getElementById('pdfPageContainer');
  var overlay       = document.getElementById('annotationOverlay');
  var listEl        = document.getElementById('annotationList');
  var listEmpty     = document.getElementById('annotationListEmpty');
  var viewerWrap    = document.getElementById('pdfViewerWrap');
  if (!pageContainer || !overlay) return;

  var annotations  = [];
  var currentScale = 1;
  var currentPage  = 1;
  var annotationMode = false;
  var pdfReady     = false;
  var autoNavDone  = false;

  /* Mobile detection — checked once at startup, reusable */
  var isMobile = !!(window.matchMedia && window.matchMedia('(pointer:coarse)').matches) ||
                 (window.innerWidth < 768);
  /* Drag needs a larger threshold on touch to distinguish tap vs drag */
  var DRAG_THRESHOLD = isMobile ? 16 : 6;

  /* ── Supervisor: annotation mode toggle ── */
  var annotateBtn  = document.getElementById('annotateToggleBtn');
  var annotateHint = document.getElementById('annotateHint');
  var PENCIL = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="flex-shrink:0"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>';

  function setAnnotationMode(on) {
    annotationMode = on;
    if (annotateBtn) {
      annotateBtn.className  = on ? 'btn btn-primary btn-sm' : 'btn btn-outline btn-sm';
      annotateBtn.style.gap  = '6px';
      annotateBtn.style.display = 'flex';
      annotateBtn.style.alignItems = 'center';
      annotateBtn.innerHTML  = PENCIL + (on ? ' Stop annotating' : ' Annotate');
    }
    if (annotateHint) {
      annotateHint.style.display = on ? '' : 'none';
      annotateHint.textContent   = on ? (isMobile ? 'Tap or drag to mark an area' : 'Click or drag to mark an area') : '';
    }
    /* Block scroll on BOTH pageContainer AND viewerWrap while annotating,
       so the browser can't scroll-cancel a touch drag mid-gesture */
    var ta = on ? 'none' : '';
    pageContainer.style.touchAction = ta;
    pageContainer.style.userSelect  = ta === 'none' ? 'none' : '';
    if (viewerWrap) viewerWrap.style.touchAction = ta;

    if (!on) {
      /* Clean up any leftover drag rect / pending state when turning off,
         so stale selections don't remain on screen */
      removeDragDiv();
      pending = null;
      if (popover) popover.classList.remove('open');
      if (commentInput) commentInput.value = '';
    }
  }

  if (annotateBtn && isSupervisor) {
    annotateBtn.addEventListener('click', function () { setAnnotationMode(!annotationMode); });
  }

  /* ── Supervisor: popover ── */
  var popover      = document.getElementById('annotationPopover');
  var commentInput = document.getElementById('annotationCommentInput');
  var saveBtn      = document.getElementById('annotationSaveBtn');
  var cancelBtn    = document.getElementById('annotationCancelBtn');

  /* ── Student: comment bubble ── */
  var bubble      = document.getElementById('annotationBubble');
  var bubbleText  = document.getElementById('annotationBubbleText');
  var bubbleMeta  = document.getElementById('annotationBubbleMeta');
  var bubbleClose = document.getElementById('annotationBubbleClose');

  /* ── Drag state ── */
  var dragStart = null;
  var dragDiv   = null;
  var pending   = null;

  /* ── utils ── */
  function toast(msg, type) {
    window.Scholaris && window.Scholaris.showToast && window.Scholaris.showToast(msg, type);
  }
  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function csrfHeaders(json) {
    var h = { 'X-CSRFToken': cfg.csrfToken };
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }
  function toPage(clientX, clientY) {
    var r = pageContainer.getBoundingClientRect();
    return { x: (clientX - r.left) / currentScale, y: (clientY - r.top) / currentScale };
  }
  /* Returns the actual visible viewport rectangle, accounting for virtual keyboard on mobile */
  function getVVP() {
    var vvp = window.visualViewport;
    if (vvp) {
      return { top: vvp.offsetTop, left: vvp.offsetLeft, width: vvp.width, height: vvp.height };
    }
    return { top: 0, left: 0, width: window.innerWidth, height: window.innerHeight };
  }

  /* ── load + render ── */
  function loadAnnotations() {
    fetch(cfg.listUrl)
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (data) {
        annotations = Array.isArray(data) ? data : [];
        if (pdfReady) {
          renderHighlights();
          maybeAutoNavigate();
        }
        renderList();
      })
      .catch(function () { annotations = []; renderList(); });
  }

  function maybeAutoNavigate() {
    if (isSupervisor || autoNavDone || annotations.length === 0) return;
    autoNavDone = true;
    var hasOnCurrent = annotations.some(function (a) { return a.page_number === currentPage; });
    if (!hasOnCurrent && cfg.goToPage) {
      var firstPage = annotations.reduce(function (min, a) {
        return a.page_number < min ? a.page_number : min;
      }, Infinity);
      if (firstPage !== Infinity) cfg.goToPage(firstPage);
    }
  }

  function renderHighlights() {
    overlay.innerHTML = '';
    annotations
      .filter(function (a) { return a.page_number === currentPage; })
      .forEach(function (a) {
        var div = document.createElement('div');
        div.className  = 'annotation-highlight' + (a.is_resolved ? ' resolved' : '');
        div.style.left   = (a.x_position * currentScale) + 'px';
        div.style.top    = (a.y_position * currentScale) + 'px';
        div.style.width  = (a.width  * currentScale) + 'px';
        div.style.height = (a.height * currentScale) + 'px';
        div.dataset.annId = a.id;

        function onHighlightActivate(e) {
          e.stopPropagation();
          pulseHighlight(a.id);
          if (isSupervisor) { scrollListTo(a.id); }
          else { openBubbleAtElement(a, div); }
        }
        div.addEventListener('click', onHighlightActivate);
        div.addEventListener('touchend', function (e) {
          if (e.changedTouches && e.changedTouches.length === 1) {
            e.preventDefault();
            onHighlightActivate(e);
          }
        });

        overlay.appendChild(div);
      });
  }

  /* ── pulse animation ── */
  function pulseHighlight(annId) {
    var hl = overlay.querySelector('[data-ann-id="' + annId + '"]');
    if (!hl) return;
    hl.classList.remove('ann-pulsing');
    void hl.offsetWidth;
    hl.classList.add('ann-pulsing');
    hl.addEventListener('animationend', function () { hl.classList.remove('ann-pulsing'); }, { once: true });
  }

  /* ── annotation list ── */
  function renderList() {
    listEl.querySelectorAll('.ann-item').forEach(function (el) { el.remove(); });
    if (listEmpty) listEmpty.style.display = annotations.length === 0 ? '' : 'none';

    annotations.forEach(function (a, idx) {
      var item = document.createElement('div');
      item.className     = 'ann-item';
      item.dataset.annId = a.id;
      item.style.cssText =
        'border:1.5px solid var(--card-light-border);border-radius:12px;' +
        'padding:12px 14px;background:var(--card-light);cursor:pointer;margin-bottom:8px;';

      var statusCls  = a.is_resolved ? 'badge-approved' : 'badge-pending';
      var statusText = a.is_resolved ? 'Resolved' : 'Open';

      item.innerHTML =
        '<div class="row" style="justify-content:space-between;align-items:center;margin-bottom:6px;">' +
          '<span style="font-size:12px;font-weight:600;color:var(--text-secondary);">' +
            '#' + (idx + 1) + ' &nbsp;&middot;&nbsp; ' +
            '<span style="color:var(--accent-gold);cursor:pointer;" class="ann-page-jump" data-page="' + a.page_number + '">' +
              'Page ' + a.page_number +
            '</span></span>' +
          '<span class="badge ' + statusCls + '">' + statusText + '</span>' +
        '</div>' +
        '<p style="font-size:13px;line-height:1.5;margin:0 0 8px;">' + esc(a.comment) + '</p>' +
        '<div class="ann-actions row" style="gap:6px;flex-wrap:wrap;"></div>';

      var pageLink = item.querySelector('.ann-page-jump');
      if (pageLink) {
        pageLink.addEventListener('click', function (e) {
          e.stopPropagation();
          activateAnnotation(a);
        });
      }

      var actions = item.querySelector('.ann-actions');

      if (!isSupervisor && !a.is_resolved) {
        var resBtn = document.createElement('button');
        resBtn.className = 'btn btn-outline btn-sm';
        resBtn.textContent = 'Mark resolved';
        resBtn.addEventListener('click', function (e) { e.stopPropagation(); resolveAnnotation(a.id); });
        actions.appendChild(resBtn);
      }
      if (isSupervisor) {
        var delBtn = document.createElement('button');
        delBtn.className = 'btn btn-outline btn-sm';
        delBtn.style.color = 'var(--danger)';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', function (e) { e.stopPropagation(); deleteAnnotation(a.id); });
        actions.appendChild(delBtn);
      }

      item.addEventListener('click', function () { activateAnnotation(a); });
      listEl.appendChild(item);
    });
  }

  function activateAnnotation(a) {
    if (a.page_number !== currentPage && cfg.goToPage) {
      var done = false;
      function onRendered(e) {
        if (done) return;
        if (e && e.detail && e.detail.pageNumber !== a.page_number) return;
        done = true;
        document.removeEventListener('pdf:rendered', onRendered);
        setTimeout(function () { afterActivate(a); }, 0);
      }
      document.addEventListener('pdf:rendered', onRendered);
      setTimeout(function () { if (!done) onRendered(null); }, 1800);
      cfg.goToPage(a.page_number);
    } else {
      afterActivate(a);
    }
  }

  function afterActivate(a) {
    var hl = overlay.querySelector('[data-ann-id="' + a.id + '"]');
    if (!hl) return;
    if (viewerWrap) viewerWrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    pulseHighlight(a.id);
    if (!isSupervisor) {
      setTimeout(function () { openBubbleAtElement(a, hl); }, 300);
    }
  }

  function scrollListTo(annId) {
    var row = listEl.querySelector('[data-ann-id="' + annId + '"]');
    if (row) row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /* ── student comment bubble ── */
  function openBubbleAtElement(a, el) {
    var r = el.getBoundingClientRect();
    openBubble(a, (r.left + r.right) / 2, r.bottom);
  }

  function openBubble(a, clientX, clientY) {
    if (!bubble) return;
    if (bubbleText) bubbleText.textContent = a.comment;
    if (bubbleMeta) {
      bubbleMeta.innerHTML =
        '<span style="font-size:12px;color:var(--text-secondary);">Page ' + a.page_number + '</span>' +
        '<span class="badge ' + (a.is_resolved ? 'badge-approved' : 'badge-pending') + '">' +
          (a.is_resolved ? 'Resolved' : 'Open') + '</span>';
    }
    var vvp = getVVP();
    var bw  = Math.min(290, vvp.width - 16);
    var bh  = 150;
    var left = clientX - bw / 2;
    var top  = clientY + 12;
    if (left + bw > vvp.left + vvp.width  - 8) left = vvp.left + vvp.width  - bw - 8;
    if (left       < vvp.left + 8)              left = vvp.left + 8;
    if (top  + bh  > vvp.top  + vvp.height - 8) top  = clientY - bh - 12;
    if (top        < vvp.top  + 8)              top  = vvp.top  + 8;
    bubble.style.width = bw + 'px';
    bubble.style.left  = left + 'px';
    bubble.style.top   = top  + 'px';
    bubble.classList.add('open');
  }

  function closeBubble() { if (bubble) bubble.classList.remove('open'); }

  /* ── API calls ── */
  function resolveAnnotation(id) {
    fetch('/annotation/' + id + '/resolve', {
      method: 'PATCH', headers: csrfHeaders(true), body: JSON.stringify({ is_resolved: true }),
    })
      .then(function (r) {
        if (r.ok) { toast('Marked as resolved.', 'success'); loadAnnotations(); }
        else toast('Could not resolve.', 'error');
      }).catch(function () { toast('Network error.', 'error'); });
  }

  function deleteAnnotation(id) {
    fetch('/annotation/' + id, { method: 'DELETE', headers: csrfHeaders(false) })
      .then(function (r) {
        if (r.ok) { toast('Annotation deleted.', 'success'); loadAnnotations(); }
        else toast('Could not delete.', 'error');
      }).catch(function () { toast('Network error.', 'error'); });
  }

  /* ── supervisor popover ── */
  function openPopover(sel, clientX, clientY) {
    if (!popover) return;
    pending = sel;

    var vvp = getVVP();

    if (isMobile) {
      /* On mobile: centre the popover in the current visual viewport
         (visualViewport.height shrinks when the keyboard appears, so
          the popover auto-clears the keyboard area) */
      var pw = Math.min(vvp.width - 24, 340);
      popover.style.width    = pw + 'px';
      popover.style.minWidth = 'unset';
      popover.style.left     = (vvp.left + (vvp.width - pw) / 2) + 'px';
      popover.style.top      = (vvp.top  + Math.round(vvp.height * 0.22)) + 'px';
    } else {
      var pw = 280, ph = 190;
      var left = clientX + 14, top = clientY + 14;
      if (left + pw > vvp.left + vvp.width  - 8) left = clientX - pw - 14;
      if (top  + ph > vvp.top  + vvp.height - 8) top  = clientY - ph - 14;
      if (left < vvp.left + 8) left = vvp.left + 8;
      if (top  < vvp.top  + 8) top  = vvp.top  + 8;
      popover.style.width    = '';
      popover.style.minWidth = '';
      popover.style.left = left + 'px';
      popover.style.top  = top  + 'px';
    }

    popover.classList.add('open');
    if (dragDiv) dragDiv.classList.add('ann-sel-locked');
    if (commentInput) {
      commentInput.value = '';
      /* Call focus() synchronously while still inside the touchend/mouseup
         handler — iOS only shows the keyboard for focus() calls that happen
         within the same user-gesture tick. setTimeout breaks this. */
      commentInput.focus();
    }
  }

  /* Recentre popover when virtual keyboard resizes visualViewport */
  if (window.visualViewport && isMobile) {
    window.visualViewport.addEventListener('resize', function () {
      if (popover && popover.classList.contains('open')) {
        var vvp = getVVP();
        var pw  = parseFloat(popover.style.width) || Math.min(vvp.width - 24, 340);
        popover.style.left = (vvp.left + (vvp.width  - pw) / 2) + 'px';
        popover.style.top  = (vvp.top  + Math.round(vvp.height * 0.22)) + 'px';
      }
    });
  }

  function closePopover(exitMode) {
    if (popover) popover.classList.remove('open');
    if (commentInput) commentInput.value = '';
    pending = null;
    removeDragDiv();
    if (exitMode) setAnnotationMode(false);
  }

  /* ── drag helpers ── */
  function removeDragDiv() {
    if (dragDiv) { dragDiv.remove(); dragDiv = null; }
    dragStart = null;
  }

  function startDrag(clientX, clientY) {
    var pos = toPage(clientX, clientY);
    dragStart = pos;
    dragDiv = document.createElement('div');
    dragDiv.style.cssText =
      'position:absolute;border:2px dashed #c9952a;background:rgba(201,149,42,.12);' +
      'pointer-events:none;z-index:10;' +
      'left:' + (pos.x * currentScale) + 'px;top:' + (pos.y * currentScale) + 'px;' +
      'width:2px;height:2px;border-radius:3px;';
    pageContainer.appendChild(dragDiv);
  }

  function moveDrag(clientX, clientY) {
    if (!dragDiv || !dragStart) return;
    if (popover && popover.classList.contains('open')) return;
    var cur = toPage(clientX, clientY);
    var x = Math.min(dragStart.x, cur.x) * currentScale;
    var y = Math.min(dragStart.y, cur.y) * currentScale;
    dragDiv.style.left   = x + 'px';
    dragDiv.style.top    = y + 'px';
    dragDiv.style.width  = (Math.abs(cur.x - dragStart.x) * currentScale) + 'px';
    dragDiv.style.height = (Math.abs(cur.y - dragStart.y) * currentScale) + 'px';
  }

  function endDrag(clientX, clientY) {
    if (!dragStart) return;
    var cur = toPage(clientX, clientY);
    var dx  = Math.abs(cur.x - dragStart.x);
    var dy  = Math.abs(cur.y - dragStart.y);

    var sel;
    if (dx > DRAG_THRESHOLD || dy > DRAG_THRESHOLD) {
      sel = {
        page_number:   currentPage,
        x:             Math.min(dragStart.x, cur.x),
        y:             Math.min(dragStart.y, cur.y),
        width:         Math.max(dx, 12),
        height:        Math.max(dy, 12),
        selected_text: '[Page ' + currentPage + ' area]',
      };
    } else {
      removeDragDiv();
      sel = {
        page_number:   currentPage,
        x:             cur.x - 12,
        y:             cur.y - 12,
        width:         24,
        height:        24,
        selected_text: '[Page ' + currentPage + ' note]',
      };
    }
    openPopover(sel, clientX, clientY);
  }

  /* ── Mouse events ── */
  function onMouseDown(e) {
    if (!isSupervisor || !annotationMode) return;
    if (popover && popover.classList.contains('open')) return;
    if (popover && popover.contains(e.target)) return;
    if (e.target.closest('.annotation-highlight')) return;
    if (e.button !== 0) return;
    closePopover();
    e.preventDefault();
    startDrag(e.clientX, e.clientY);
  }

  function onMouseMove(e) {
    if (popover && popover.classList.contains('open')) return;
    moveDrag(e.clientX, e.clientY);
  }

  function onMouseUp(e) {
    if (!isSupervisor || !annotationMode || !dragStart) return;
    if (popover && popover.classList.contains('open')) return;
    if (popover && popover.contains(e.target)) return;
    endDrag(e.clientX, e.clientY);
  }

  /* ── Touch events ── */
  function onTouchStart(e) {
    if (!isSupervisor || !annotationMode) return;
    if (e.touches.length > 1) { removeDragDiv(); return; }  /* cancel on pinch */
    if (popover && popover.classList.contains('open')) return;
    if (popover && popover.contains(e.target)) return;
    if (e.target.closest('.annotation-highlight')) return;
    e.preventDefault();
    closePopover();
    var t = e.touches[0];
    startDrag(t.clientX, t.clientY);
  }

  function onTouchMove(e) {
    if (!dragStart) return;
    if (e.touches.length > 1) { removeDragDiv(); return; }  /* cancel on pinch */
    if (popover && popover.classList.contains('open')) return;
    e.preventDefault();
    var t = e.touches[0];
    moveDrag(t.clientX, t.clientY);
  }

  function onTouchEnd(e) {
    if (!isSupervisor || !annotationMode || !dragStart) return;
    if (popover && popover.classList.contains('open')) return;
    /* Do NOT call e.preventDefault() here — iOS requires the synthetic click
       that fires after touchend to be un-cancelled so that programmatic
       focus() inside openPopover() is treated as a valid keyboard trigger. */
    var t = e.changedTouches[0];
    endDrag(t.clientX, t.clientY);
  }

  pageContainer.addEventListener('contextmenu', function (e) {
    if (annotationMode) { e.preventDefault(); removeDragDiv(); }
  });

  /* ── save ── */
  function saveAnnotation() {
    if (!pending) { toast('Tap or drag on the PDF to mark an area first.', 'error'); return; }
    var text = commentInput ? commentInput.value.trim() : '';
    if (!text) { toast('Write a comment before saving.', 'error'); return; }

    if (saveBtn) { saveBtn.disabled = true; saveBtn.classList.add('is-loading'); }

    fetch(cfg.saveUrl, {
      method: 'POST',
      headers: csrfHeaders(true),
      body: JSON.stringify({
        submission_id: cfg.submissionId,
        page_number:   pending.page_number,
        x: pending.x, y: pending.y,
        width: pending.width, height: pending.height,
        selected_text: pending.selected_text,
        comment: text,
      }),
    })
      .then(function (r) {
        if (r.ok) {
          toast('Comment saved.', 'success');
          closePopover(true);
          loadAnnotations();
        } else {
          return r.json().catch(function () { return {}; }).then(function (err) {
            toast(err.error || 'Could not save comment.', 'error');
          });
        }
      })
      .catch(function () { toast('Network error.', 'error'); })
      .finally(function () {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.classList.remove('is-loading'); }
      });
  }

  /* ── pdf:rendered ── */
  document.addEventListener('pdf:rendered', function (e) {
    currentScale = e.detail.scale;
    currentPage  = e.detail.pageNumber;
    /* On Android, the virtual keyboard opening fires window.resize which
       causes pdf-viewer.js to re-render, which fires pdf:rendered.
       Don't close the annotation popover if the supervisor is mid-annotation
       (pending is set), otherwise the comment textarea disappears on tap. */
    if (!pending) closePopover();
    closeBubble();

    var firstTime = !pdfReady;
    pdfReady = true;

    renderHighlights();

    if (firstTime && annotations.length > 0) {
      maybeAutoNavigate();
    }
  });

  if (isSupervisor) {
    pageContainer.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    pageContainer.addEventListener('touchstart', onTouchStart, { passive: false });
    pageContainer.addEventListener('touchmove',  onTouchMove,  { passive: false });
    pageContainer.addEventListener('touchend',   onTouchEnd,   { passive: false });
  }

  /* Close bubble when tapping outside it */
  document.addEventListener('mousedown', function (e) {
    if (bubble && bubble.classList.contains('open') &&
        !bubble.contains(e.target) && !overlay.contains(e.target)) {
      closeBubble();
    }
  });
  document.addEventListener('touchstart', function (e) {
    if (bubble && bubble.classList.contains('open') &&
        !bubble.contains(e.target) && !overlay.contains(e.target)) {
      closeBubble();
    }
  }, { passive: true });

  if (saveBtn)     saveBtn.addEventListener('click', saveAnnotation);
  if (cancelBtn)   cancelBtn.addEventListener('click', function () { closePopover(); });
  if (bubbleClose) bubbleClose.addEventListener('click', closeBubble);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closePopover(); closeBubble(); }
  });

  loadAnnotations();
})();
