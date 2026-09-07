(function () {
  'use strict';

  /* ── Inject styles once ── */
  if (!document.getElementById('cs-styles')) {
    var s = document.createElement('style');
    s.id = 'cs-styles';
    s.textContent =
      /* Hide the native select in-place */
      '.cs-hidden{display:none !important;}' +

      /* Widget wrapper */
      '.cs-wrap{position:relative;width:100%;font-family:inherit;}' +

      /* Trigger button — base (light mode) */
      '.cs-btn{' +
        'width:100%;display:flex;align-items:center;justify-content:space-between;gap:10px;' +
        'padding:13px 16px;' +
        'background:var(--card-light,#fff);' +
        'border:1.5px solid var(--card-light-border,rgba(15,15,16,.1));' +
        'border-radius:11px;' +
        'color:var(--text-primary,#15161a);' +
        'font-family:inherit;font-size:14px;' +
        'cursor:pointer;text-align:left;' +
        'transition:border-color 180ms,background 180ms,box-shadow 180ms;' +
        'outline:none;' +
        'box-sizing:border-box;' +
      '}' +
      '.cs-btn:hover{border-color:rgba(201,149,42,.42);}' +
      '.cs-btn:focus-visible{box-shadow:0 0 0 3px rgba(201,149,42,.22);}' +
      '.cs-wrap.cs-open .cs-btn{' +
        'border-color:rgba(201,149,42,.65);' +
        'box-shadow:0 0 0 3px rgba(201,149,42,.12);' +
      '}' +

      /* Label & arrow inside button */
      '.cs-lbl{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;transition:color 150ms;}' +
      '.cs-lbl.cs-ph{color:var(--text-secondary,#9a9a9a);}' +
      '.cs-arr{flex-shrink:0;color:var(--text-secondary,#9a9a9a);transition:transform 240ms cubic-bezier(.16,1,.3,1),color 180ms;}' +
      '.cs-wrap.cs-open .cs-arr{transform:rotate(180deg);color:#c9952a;}' +

      /* Floating dropdown panel */
      '.cs-panel{' +
        'position:fixed;' +
        'background:var(--card-light,#fff);' +
        'border:1.5px solid var(--card-light-border,rgba(15,15,16,.1));' +
        'border-radius:14px;' +
        'box-shadow:0 20px 60px rgba(19,21,26,.2),0 4px 16px rgba(19,21,26,.12);' +
        'max-height:260px;overflow-y:auto;' +
        'z-index:9999;padding:6px;margin:0;list-style:none;' +
        'opacity:0;transform:translateY(-8px) scale(.98);pointer-events:none;' +
        'transition:opacity 200ms cubic-bezier(.16,1,.3,1),transform 200ms cubic-bezier(.16,1,.3,1);' +
        'transform-origin:top center;' +
        'backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);' +
      '}' +
      '.cs-panel.cs-open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto;}' +

      /* Option rows */
      '.cs-opt{' +
        'display:flex;align-items:center;justify-content:space-between;gap:8px;' +
        'padding:10px 14px;border-radius:9px;' +
        'cursor:pointer;font-size:13.5px;' +
        'color:var(--text-primary,#15161a);' +
        'transition:background 120ms,color 120ms;user-select:none;' +
      '}' +
      '.cs-opt:hover,.cs-opt.cs-focused{background:rgba(201,149,42,.1);}' +
      '.cs-opt.cs-sel{color:#c9952a;font-weight:600;}' +
      '.cs-opt.cs-ph-opt{color:var(--text-secondary,#9a9a9a);font-style:italic;}' +
      '.cs-chk{flex-shrink:0;opacity:0;color:#c9952a;transition:opacity 120ms;}' +
      '.cs-opt.cs-sel .cs-chk{opacity:1;}' +

      /* Scrollbar */
      '.cs-panel::-webkit-scrollbar{width:4px;}' +
      '.cs-panel::-webkit-scrollbar-track{background:transparent;}' +
      '.cs-panel::-webkit-scrollbar-thumb{background:rgba(201,149,42,.3);border-radius:2px;}' +

      /* ── Dark panel variant (register page / dark contexts) ── */
      '.cs-dark.cs-panel{' +
        'background:rgba(12,10,18,.95);' +
        'border-color:rgba(200,164,126,.18);' +
        'box-shadow:0 20px 60px rgba(0,0,0,.7),0 0 0 1px rgba(200,164,126,.07);' +
      '}' +
      '.cs-dark .cs-opt{color:rgba(240,237,232,.7);}' +
      '.cs-dark .cs-opt:hover,.cs-dark .cs-opt.cs-focused{background:rgba(200,164,126,.13);color:#f0ede8;}' +
      '.cs-dark .cs-opt.cs-sel{color:#c8a47e;}' +
      '.cs-dark .cs-opt.cs-ph-opt{color:rgba(240,237,232,.3);}' +
      '.cs-dark .cs-chk{color:#c8a47e;}' +

      /* ── Register page trigger (inside .asl-wrap) ── */
      '.asl-wrap .cs-btn{' +
        'background:rgba(255,255,255,.055);' +
        'border:1px solid rgba(255,255,255,.1);' +
        'border-radius:11px;' +
        'color:#f0ede8;' +
      '}' +
      '.asl-wrap .cs-btn:hover{border-color:rgba(200,164,126,.55);background:rgba(200,164,126,.04);}' +
      '.asl-wrap .cs-wrap.cs-open .cs-btn{' +
        'border-color:rgba(200,164,126,.65);background:rgba(200,164,126,.04);' +
        'box-shadow:0 0 0 3px rgba(200,164,126,.1);' +
      '}' +
      '.asl-wrap .cs-lbl.cs-ph{color:rgba(240,237,232,.28);}' +
      '.asl-wrap .cs-lbl{color:#f0ede8;}' +
      '.asl-wrap .cs-arr{color:rgba(240,237,232,.35);}' +
      '.asl-wrap .cs-wrap.cs-open .cs-arr{color:#c8a47e;}' +

      /* ── App dark theme ── */
      '[data-theme="dark"] .cs-btn{' +
        'background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.09);color:#f4f5f7;' +
      '}' +
      '[data-theme="dark"] .cs-btn:hover{border-color:rgba(201,149,42,.38);}' +
      '[data-theme="dark"] .cs-wrap.cs-open .cs-btn{border-color:rgba(201,149,42,.58);}' +
      '[data-theme="dark"] .cs-lbl.cs-ph{color:rgba(244,245,247,.3);}' +
      '[data-theme="dark"] .cs-panel{' +
        'background:rgba(18,20,28,.97);border-color:rgba(255,255,255,.09);' +
        'box-shadow:0 20px 60px rgba(0,0,0,.6);' +
      '}' +
      '[data-theme="dark"] .cs-opt{color:rgba(244,245,247,.72);}' +
      '[data-theme="dark"] .cs-opt:hover,[data-theme="dark"] .cs-opt.cs-focused{' +
        'background:rgba(201,149,42,.12);color:#f4f5f7;' +
      '}' +
      '[data-theme="dark"] .cs-opt.cs-sel{color:#c9952a;}' +
      '[data-theme="dark"] .cs-opt.cs-ph-opt{color:rgba(244,245,247,.28);}';

    document.head.appendChild(s);
  }

  /* ── Tiny SVG helper ── */
  function mkSvg(d, sw) {
    var ns = 'http://www.w3.org/2000/svg';
    var el = document.createElementNS(ns, 'svg');
    el.setAttribute('width', '14'); el.setAttribute('height', '14');
    el.setAttribute('viewBox', '0 0 24 24'); el.setAttribute('fill', 'none');
    el.setAttribute('stroke', 'currentColor');
    el.setAttribute('stroke-width', sw || '2.2');
    el.setAttribute('stroke-linecap', 'round'); el.setAttribute('stroke-linejoin', 'round');
    var p = document.createElementNS(ns, 'path');
    p.setAttribute('d', d);
    el.appendChild(p);
    return el;
  }

  /* ── Build one custom select ── */
  function build(select) {
    if (select._csBuilt) return;
    select._csBuilt = true;

    /* Detect dark register-page context */
    var inAslWrap = !!select.closest('.asl-wrap');

    /* Hide native select — keep it in DOM for form submission */
    select.classList.add('cs-hidden');

    /* Build the widget wrapper + trigger */
    var wrap = document.createElement('div');
    wrap.className = 'cs-wrap';

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'cs-btn';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');

    var lbl = document.createElement('span');
    lbl.className = 'cs-lbl cs-ph';

    var arr = mkSvg('M6 9l6 6 6-6');
    arr.setAttribute('class', 'cs-arr');

    btn.appendChild(lbl);
    btn.appendChild(arr);
    wrap.appendChild(btn);

    /* Insert wrap immediately before the hidden select */
    select.parentNode.insertBefore(wrap, select);

    /* Build floating panel (teleported to body when open) */
    var panel = document.createElement('ul');
    panel.setAttribute('role', 'listbox');
    panel.className = 'cs-panel' + (inAslWrap ? ' cs-dark' : '');

    var opts = Array.from(select.options);
    var rows = opts.map(function (opt, i) {
      var li = document.createElement('li');
      li.className = 'cs-opt' + (opt.value === '' ? ' cs-ph-opt' : '');
      li.setAttribute('role', 'option');
      li.setAttribute('data-val', opt.value);

      var span = document.createElement('span');
      span.textContent = opt.text;

      var chk = mkSvg('M20 6L9 17l-5-5', '2.5');
      chk.setAttribute('class', 'cs-chk');

      li.appendChild(span);
      li.appendChild(chk);
      panel.appendChild(li);
      return li;
    });

    /* ── State ── */
    var open = false;
    var focIdx = -1;

    function syncBtn() {
      var sel = select.options[select.selectedIndex];
      var isPhaceholder = !sel || sel.value === '';
      lbl.textContent = sel ? sel.text : '';
      lbl.className = 'cs-lbl' + (isPhaceholder ? ' cs-ph' : '');
      rows.forEach(function (li, i) {
        var on = opts[i].value === select.value;
        li.classList.toggle('cs-sel', on);
        li.setAttribute('aria-selected', on ? 'true' : 'false');
      });
    }
    syncBtn();

    function placePanel() {
      var r = btn.getBoundingClientRect();
      panel.style.top  = (r.bottom + 5) + 'px';
      panel.style.left = r.left + 'px';
      panel.style.width = r.width + 'px';
    }

    function hl() {
      rows.forEach(function (li, i) { li.classList.toggle('cs-focused', i === focIdx); });
      if (rows[focIdx]) rows[focIdx].scrollIntoView({ block: 'nearest' });
    }

    function openMenu() {
      if (open) return;
      open = true;
      document.body.appendChild(panel);
      placePanel();
      panel.getBoundingClientRect(); /* force reflow */
      panel.classList.add('cs-open');
      wrap.classList.add('cs-open');
      btn.setAttribute('aria-expanded', 'true');
      focIdx = rows.findIndex(function (li) { return li.classList.contains('cs-sel'); });
      if (focIdx < 0) focIdx = 0;
      hl();
      window.addEventListener('scroll', placePanel, { passive: true, capture: true });
      window.addEventListener('resize', placePanel, { passive: true });
    }

    function closeMenu() {
      if (!open) return;
      open = false;
      panel.classList.remove('cs-open');
      wrap.classList.remove('cs-open');
      btn.setAttribute('aria-expanded', 'false');
      rows.forEach(function (li) { li.classList.remove('cs-focused'); });
      window.removeEventListener('scroll', placePanel, { capture: true });
      window.removeEventListener('resize', placePanel);
      setTimeout(function () {
        if (!open && panel.parentNode === document.body) document.body.removeChild(panel);
      }, 210);
    }

    function pick(idx) {
      var li = rows[idx];
      if (!li) return;
      select.value = li.getAttribute('data-val');
      select.dispatchEvent(new Event('change', { bubbles: true }));
      syncBtn();
      closeMenu();
      btn.focus();
    }

    /* ── Events ── */
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      open ? closeMenu() : openMenu();
    });

    rows.forEach(function (li, i) {
      li.addEventListener('mousedown', function (e) { e.preventDefault(); }); /* keep focus on btn */
      li.addEventListener('click', function (e) { e.stopPropagation(); pick(i); });
      li.addEventListener('mouseenter', function () { focIdx = i; hl(); });
    });

    btn.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        open ? pick(focIdx) : openMenu();
      } else if (e.key === 'Escape') {
        closeMenu();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (!open) { openMenu(); return; }
        focIdx = Math.min(focIdx + 1, rows.length - 1);
        hl();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (!open) { openMenu(); return; }
        focIdx = Math.max(focIdx - 1, 0);
        hl();
      } else if (e.key === 'Tab') {
        closeMenu();
      }
    });

    document.addEventListener('click', function (e) {
      if (open && !wrap.contains(e.target) && !panel.contains(e.target)) closeMenu();
    });

    select.addEventListener('change', syncBtn);
  }

  /* ── Init all matching selects ── */
  function init(root) {
    (root || document).querySelectorAll('select:not([multiple]):not([data-no-cs])').forEach(build);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(); });
  } else {
    init();
  }

  window.ScholariCS = { init: init };
})();
