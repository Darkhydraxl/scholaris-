(function () {
  function csrfToken() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.content : '';
  }
  window.Scholaris = window.Scholaris || {};
  window.Scholaris.csrfToken = csrfToken;

  // ---- Mobile sidebar (locks background scroll while open, like Twitter's drawer) ----
  document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('sidebar');
    const hamburger = document.getElementById('hamburgerBtn');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar || !hamburger || !backdrop) return;

    let lockedScrollY = 0;

    function lockBodyScroll() {
      lockedScrollY = window.scrollY;
      document.body.style.position = 'fixed';
      document.body.style.top = `-${lockedScrollY}px`;
      document.body.style.left = '0';
      document.body.style.right = '0';
      document.body.style.width = '100%';
    }

    function unlockBodyScroll() {
      document.body.style.position = '';
      document.body.style.top = '';
      document.body.style.left = '';
      document.body.style.right = '';
      document.body.style.width = '';
      // Defer to the next frame: the document's scrollable height hasn't been
      // recalculated yet in this tick (it was clamped while position:fixed
      // was active), so an immediate scrollTo would clamp to 0.
      requestAnimationFrame(() => window.scrollTo(0, lockedScrollY));
    }

    function openSidebar() {
      sidebar.classList.add('open');
      backdrop.classList.add('open');
      lockBodyScroll();
    }

    function closeSidebar() {
      sidebar.classList.remove('open');
      backdrop.classList.remove('open');
      unlockBodyScroll();
    }

    hamburger.addEventListener('click', openSidebar);
    backdrop.addEventListener('click', closeSidebar);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && sidebar.classList.contains('open')) closeSidebar();
    });
  });

  // ---- Active nav pill: animated background that morphs between items ----
  document.addEventListener('DOMContentLoaded', () => {
    const navList = document.getElementById('navListPrimary');
    if (!navList) return;
    const active = navList.querySelector('.nav-item.active');
    if (!active) return;
    let pill = navList.querySelector('.nav-pill');
    if (!pill) {
      pill = document.createElement('div');
      pill.className = 'nav-pill';
      navList.insertBefore(pill, navList.firstChild);
    }
    function positionPill(target, instant) {
      const navRect = navList.getBoundingClientRect();
      const itemRect = target.getBoundingClientRect();
      const top = itemRect.top - navRect.top;
      if (instant) pill.style.transition = 'none';
      pill.style.transform = `translateY(${top}px)`;
      pill.style.height = `${itemRect.height}px`;
      if (instant) requestAnimationFrame(() => { pill.style.transition = ''; });
    }
    positionPill(active, true);
    // Keep the .active class (it supplies the contrasting text color) but let
    // the separately animated .nav-pill element supply the background so the
    // pill can morph smoothly between items on future navigations.
    active.style.background = 'transparent';
    active.style.position = 'relative';
    active.style.zIndex = '1';
  });

  // ---- Loading spinner on any button/link marked .js-submit-btn within a form ----
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form').forEach((form) => {
      form.addEventListener('submit', () => {
        const btn = form.querySelector('.js-submit-btn');
        if (btn) {
          btn.classList.add('is-loading');
          btn.disabled = true;
        }
      });
    });
  });

  // ---- Generic confirm modal (data-confirm-title / data-confirm-body / data-confirm-url / data-confirm-method) ----
  document.addEventListener('DOMContentLoaded', () => {
    const backdrop = document.getElementById('confirmModalBackdrop');
    if (!backdrop) return;
    const titleEl = document.getElementById('confirmModalTitle');
    const bodyEl = document.getElementById('confirmModalBody');
    const acceptBtn = document.getElementById('confirmModalAccept');
    const cancelBtn = document.getElementById('confirmModalCancel');
    const closeBtn = document.getElementById('confirmModalClose');
    let pendingAction = null;

    function open() { backdrop.classList.add('open'); }
    function close() { backdrop.classList.remove('open'); pendingAction = null; }

    document.body.addEventListener('click', (e) => {
      const trigger = e.target.closest('[data-confirm-url]');
      if (!trigger) return;
      e.preventDefault();
      titleEl.textContent = trigger.dataset.confirmTitle || 'Are you sure?';
      bodyEl.textContent = trigger.dataset.confirmBody || 'This action cannot be undone.';
      pendingAction = {
        url: trigger.dataset.confirmUrl,
        method: trigger.dataset.confirmMethod || 'POST',
        redirect: trigger.dataset.confirmRedirect,
      };
      open();
    });

    acceptBtn.addEventListener('click', async () => {
      if (!pendingAction) return close();
      acceptBtn.classList.add('is-loading');
      acceptBtn.disabled = true;
      try {
        const res = await fetch(pendingAction.url, {
          method: pendingAction.method,
          headers: { 'X-CSRFToken': csrfToken() },
        });
        if (res.ok) {
          window.Scholaris.showToast('Action completed.', 'success');
          if (pendingAction.redirect) {
            window.location.href = pendingAction.redirect;
          } else {
            setTimeout(() => window.location.reload(), 400);
          }
        } else {
          window.Scholaris.showToast('Something went wrong.', 'error');
        }
      } catch (e) {
        window.Scholaris.showToast('Network error.', 'error');
      } finally {
        acceptBtn.classList.remove('is-loading');
        acceptBtn.disabled = false;
        close();
      }
    });
    cancelBtn.addEventListener('click', close);
    closeBtn.addEventListener('click', close);
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && backdrop.classList.contains('open')) close();
    });
  });

  // ---- Popover (3-dot) menus ----
  document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', (e) => {
      const trigger = e.target.closest('.menu-trigger');
      document.querySelectorAll('.popover-menu.open').forEach((m) => {
        if (!trigger || m !== trigger.nextElementSibling) m.classList.remove('open');
      });
      if (trigger) {
        const menu = trigger.nextElementSibling;
        if (menu && menu.classList.contains('popover-menu')) {
          menu.classList.toggle('open');
        }
      } else if (!e.target.closest('.popover-menu')) {
        document.querySelectorAll('.popover-menu.open').forEach((m) => m.classList.remove('open'));
      }
    });
  });

  // ---- Notification bell: poll unread count every 30s, pause when tab hidden ----
  document.addEventListener('DOMContentLoaded', () => {
    const badgeHolder = document.getElementById('notifBellBtn');
    if (!badgeHolder) return;
    let intervalId = null;

    async function pollUnread() {
      try {
        const res = await fetch('/notification/unread-count');
        if (!res.ok) return;
        const data = await res.json();
        let badge = document.getElementById('notifBadge');
        const icon = document.getElementById('notifBellIcon');
        if (data.unread_count > 0) {
          if (!badge) {
            badge = document.createElement('span');
            badge.className = 'notif-badge';
            badge.id = 'notifBadge';
            badgeHolder.appendChild(badge);
          }
          badge.textContent = data.unread_count < 10 ? data.unread_count : '9+';
          icon && icon.classList.add('bell-has-unread');
        } else if (badge) {
          badge.remove();
          icon && icon.classList.remove('bell-has-unread');
        }
      } catch (e) { /* ignore transient network errors */ }
    }

    function start() {
      if (intervalId) return;
      intervalId = setInterval(pollUnread, 30000);
    }
    function stop() {
      clearInterval(intervalId);
      intervalId = null;
    }
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) stop(); else { pollUnread(); start(); }
    });
    start();

    badgeHolder.addEventListener('click', () => { window.location.href = '/notification/'; });
  });

  // ---- Mark-as-read buttons on the notifications page ----
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.js-mark-read').forEach((btn) => {
      btn.addEventListener('click', async () => {
        btn.classList.add('is-loading');
        try {
          await fetch(btn.dataset.url, { method: 'PATCH', headers: { 'X-CSRFToken': csrfToken() } });
          const row = btn.closest('.notification-row');
          if (row) {
            row.classList.remove('unread');
            const iconCircle = row.querySelector('.nf-icon-circle');
            if (iconCircle) {
              iconCircle.className = 'nf-icon-circle nf-icon-read';
              iconCircle.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12l5 5L20 6"/></svg>';
            }
          }
          btn.remove();
        } catch (e) { window.Scholaris.showToast('Could not mark as read.', 'error'); }
      });
    });
    const markAll = document.getElementById('markAllReadBtn');
    markAll && markAll.addEventListener('click', async (e) => {
      e.preventDefault();
      markAll.classList.add('is-loading');
      try {
        await fetch(markAll.dataset.url, { method: 'POST', headers: { 'X-CSRFToken': csrfToken() } });
        window.location.reload();
      } catch (e) { window.Scholaris.showToast('Could not mark all as read.', 'error'); }
    });
  });

  // ---- Session timeout: drift-free countdown driven by an absolute server timestamp ----
  document.addEventListener('DOMContentLoaded', () => {
    const meta = document.getElementById('sessionMeta');
    if (!meta || !meta.dataset.expiresAt) return;
    const expiresAt = new Date(meta.dataset.expiresAt).getTime();
    const warnBackdrop = document.getElementById('sessionWarningBackdrop');
    const countdownEl = document.getElementById('sessionCountdown');
    const extendBtn = document.getElementById('extendSessionBtn');
    const WARNING_MS = 5 * 60 * 1000; // show warning in the final 5 minutes
    let warned = false;

    function tick() {
      const msLeft = expiresAt - Date.now();
      if (msLeft <= 0) {
        window.location.href = '/logout';
        return;
      }
      if (msLeft <= WARNING_MS) {
        if (!warned) { warnBackdrop.classList.add('open'); warned = true; }
        const totalSeconds = Math.floor(msLeft / 1000);
        const mm = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
        const ss = String(totalSeconds % 60).padStart(2, '0');
        countdownEl.textContent = `${mm}:${ss}`;
      }
      setTimeout(tick, 1000);
    }
    tick();

    extendBtn && extendBtn.addEventListener('click', async () => {
      extendBtn.classList.add('is-loading');
      try {
        const res = await fetch('/session/extend', { method: 'POST', headers: { 'X-CSRFToken': csrfToken() } });
        const data = await res.json();
        meta.dataset.expiresAt = data.expires_at;
        warnBackdrop.classList.remove('open');
        warned = false;
        window.location.reload();
      } catch (e) {
        window.Scholaris.showToast('Could not extend session.', 'error');
      } finally {
        extendBtn.classList.remove('is-loading');
      }
    });
  });
})();
