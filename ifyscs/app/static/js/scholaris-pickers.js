/* ============================================================================
   Scholaris pickers — one date calendar and one time list, shared by every
   surface that needs them. Extracted from admin/deadlines.html.

   Both submit what the server expects: the date as Y-m-d, the time as HH:MM.
   Each shows a friendlier string to the reader and keeps the machine value in
   a field of its own, so the display can read "9:30 AM" without the backend
   having to parse it.
   ========================================================================= */
(function () {
  'use strict';

  const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];

  /* ── Date ──────────────────────────────────────────────────────────────── */

  // Flatpickr's month <select> cannot be styled to match the panel, so it is
  // swapped for text and kept in sync with the arrows.
  function replaceMonthSelect(fp) {
    const sel = fp.calendarContainer.querySelector('.flatpickr-monthDropdown-months');
    if (!sel || sel._replaced) return;
    sel._replaced = true;
    const span = document.createElement('span');
    span.className = 'fp-month-text';
    const update = () => { span.textContent = MONTH_NAMES[fp.currentMonth] || ''; };
    update();
    sel.parentNode.insertBefore(span, sel);
    sel.style.cssText = 'position:absolute;opacity:0;pointer-events:none;width:0;height:0;';
    fp.calendarContainer.querySelectorAll('.flatpickr-prev-month, .flatpickr-next-month')
      .forEach(btn => btn.addEventListener('click', () => requestAnimationFrame(update)));
  }

  function datePicker(selector, extra) {
    if (typeof flatpickr === 'undefined') return null;
    const config = Object.assign({
      dateFormat: 'Y-m-d',
      altInput: true,
      altFormat: 'F j, Y',
      disableMobile: true,
      onReady(_, __, fp) { replaceMonthSelect(fp); },
      onChange(dates, _str, fp) {
        const visible = fp.altInput || fp.input;
        const wrap = visible.closest('.date-field');
        if (wrap) wrap.classList.toggle('has-val', dates.length > 0);
      },
    }, extra || {});

    const instances = flatpickr(selector, config);
    // Mark fields that arrived with a value so the label starts raised.
    const list = Array.isArray(instances) ? instances : [instances];
    list.forEach(fp => {
      if (fp && fp.input && fp.input.value) {
        const wrap = (fp.altInput || fp.input).closest('.date-field');
        if (wrap) wrap.classList.add('has-val');
      }
    });
    return instances;
  }

  /* ── Time ──────────────────────────────────────────────────────────────── */

  function label12(hour, minute) {
    const meridiem = hour < 12 ? 'AM' : 'PM';
    let h = hour % 12;
    if (h === 0) h = 12;
    return { text: h + ':' + String(minute).padStart(2, '0'), meridiem: meridiem };
  }

  function timeSelect(root) {
    if (!root || root._tsBound) return null;
    root._tsBound = true;

    const display = root.querySelector('.ts-display');
    const hidden = root.querySelector('.ts-value');
    const panel = root.querySelector('.ts-panel');
    const list = root.querySelector('.ts-list');
    if (!display || !hidden || !panel || !list) return null;

    const step = parseInt(root.dataset.step, 10) || 15;
    const options = [];

    for (let minutes = 0; minutes < 24 * 60; minutes += step) {
      const h = Math.floor(minutes / 60);
      const m = minutes % 60;
      const value = String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
      const { text, meridiem } = label12(h, m);

      const li = document.createElement('li');
      li.className = 'ts-option';
      li.setAttribute('role', 'option');
      li.dataset.value = value;
      li.innerHTML = '<span>' + text + '</span><span class="ts-meridiem">' + meridiem + '</span>';
      list.appendChild(li);
      options.push({ value: value, label: text + ' ' + meridiem, el: li });
    }

    let activeIndex = -1;

    function indexOfValue(value) {
      return options.findIndex(o => o.value === value);
    }

    function paint() {
      const current = hidden.value;
      options.forEach((o, i) => {
        o.el.classList.toggle('is-selected', o.value === current && current !== '');
        o.el.classList.toggle('is-active', i === activeIndex);
        o.el.setAttribute('aria-selected', String(o.value === current && current !== ''));
      });
    }

    function setValue(value, { commit = true } = {}) {
      const i = indexOfValue(value);
      if (i < 0) return;
      hidden.value = options[i].value;
      display.value = options[i].label;
      root.classList.add('has-val');
      activeIndex = i;
      paint();
      if (commit) {
        hidden.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }

    function scrollActiveIntoView() {
      if (activeIndex < 0) return;
      const el = options[activeIndex].el;
      const top = el.offsetTop;
      const bottom = top + el.offsetHeight;
      if (top < list.scrollTop) {
        list.scrollTop = top - 8;
      } else if (bottom > list.scrollTop + list.clientHeight) {
        list.scrollTop = bottom - list.clientHeight + 8;
      }
    }

    function open() {
      if (panel.classList.contains('is-open')) return;
      // Flip upward when there is not enough room below.
      const spaceBelow = window.innerHeight - root.getBoundingClientRect().bottom;
      panel.classList.toggle('drop-up', spaceBelow < 260);
      panel.classList.add('is-open');
      root.classList.add('is-open');
      display.setAttribute('aria-expanded', 'true');
      if (activeIndex < 0) activeIndex = Math.max(indexOfValue(hidden.value), 0);
      paint();
      requestAnimationFrame(scrollActiveIntoView);
    }

    function close() {
      panel.classList.remove('is-open');
      root.classList.remove('is-open');
      display.setAttribute('aria-expanded', 'false');
    }

    function toggle() {
      panel.classList.contains('is-open') ? close() : open();
    }

    display.addEventListener('click', toggle);
    display.addEventListener('mousedown', e => e.preventDefault()); // no caret in a readonly field

    list.addEventListener('click', e => {
      const li = e.target.closest('.ts-option');
      if (!li) return;
      setValue(li.dataset.value);
      close();
      display.focus();
    });

    // Typing digits jumps to the nearest hour, the way a native select does.
    let typed = '';
    let typedAt = 0;

    display.addEventListener('keydown', e => {
      const isOpen = panel.classList.contains('is-open');

      if (e.key === 'Escape') {
        if (isOpen) { e.preventDefault(); close(); }
        return;
      }
      if (e.key === 'Tab') { close(); return; }

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!isOpen) { open(); return; }
        const delta = e.key === 'ArrowDown' ? 1 : -1;
        activeIndex = Math.min(options.length - 1, Math.max(0, activeIndex + delta));
        paint();
        scrollActiveIntoView();
        return;
      }
      if (e.key === 'Home' || e.key === 'End') {
        if (!isOpen) return;
        e.preventDefault();
        activeIndex = e.key === 'Home' ? 0 : options.length - 1;
        paint();
        scrollActiveIntoView();
        return;
      }
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (!isOpen) { open(); return; }
        if (activeIndex >= 0) { setValue(options[activeIndex].value); close(); }
        return;
      }
      if (/^[0-9]$/.test(e.key)) {
        e.preventDefault();
        const now = Date.now();
        typed = (now - typedAt < 1000) ? (typed + e.key).slice(-2) : e.key;
        typedAt = now;
        const hour = Math.min(23, parseInt(typed, 10));
        const i = options.findIndex(o => parseInt(o.value.slice(0, 2), 10) === hour);
        if (i >= 0) {
          if (!isOpen) open();
          activeIndex = i;
          paint();
          scrollActiveIntoView();
        }
      }
    });

    document.addEventListener('click', e => {
      if (!root.contains(e.target)) close();
    });

    // Restore a value the server rendered (e.g. after a validation error).
    if (hidden.value) {
      const existing = hidden.value.slice(0, 5);
      if (indexOfValue(existing) >= 0) {
        setValue(existing, { commit: false });
      } else {
        // Not on the step grid — show it rather than silently dropping it.
        const [h, m] = existing.split(':').map(Number);
        if (!Number.isNaN(h) && !Number.isNaN(m)) {
          const { text, meridiem } = label12(h, m);
          display.value = text + ' ' + meridiem;
          root.classList.add('has-val');
        }
      }
    }

    paint();
    return { setValue, open, close };
  }

  function initAll(scope) {
    (scope || document).querySelectorAll('[data-time-select]').forEach(timeSelect);
  }

  window.Scholaris = window.Scholaris || {};
  window.Scholaris.datePicker = datePicker;
  window.Scholaris.timeSelect = timeSelect;
  window.Scholaris.initPickers = initAll;

  document.addEventListener('DOMContentLoaded', () => initAll(document));
})();
