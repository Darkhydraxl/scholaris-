/**
 * ScrollStack — vanilla JS port of the React Bits ScrollStack component.
 * Mobile-only (≤768 px). Targets elements with class `ss-card`.
 *
 * Cards pin at the first card's natural starting position, then each
 * subsequent card slides over the previous ones and pins ITEM_STACK_GAP px
 * lower, creating a layered deck effect as the user scrolls.
 */
(function () {
  'use strict';

  var ITEM_DISTANCE  = 88;   // extra margin-bottom added between cards
  var ITEM_STACK_GAP = 22;   // px each stacked card peeks above the next
  var BASE_SCALE     = 0.88;
  var ITEM_SCALE     = 0.03;
  var SCALE_PX       = 160;  // scroll px over which each card's scale transition completes

  var destroyFn = null;
  var booted    = false;

  /* ── helpers ─────────────────────────────────────────────────── */

  function isMobile() { return window.innerWidth <= 768; }

  function getScrollTop() {
    return Math.max(
      window.pageYOffset                  || 0,
      document.documentElement.scrollTop || 0,
      document.body.scrollTop            || 0,
      (function () {
        var m = document.querySelector('.app-main');
        return m ? (m.scrollTop || 0) : 0;
      }())
    );
  }

  /* ── core ────────────────────────────────────────────────────── */

  function initStack() {
    var cards = Array.from(document.querySelectorAll('.ss-card'));
    if (cards.length < 2) return null;

    /* snapshot original inline styles for cleanup */
    var snap = cards.map(function (c) {
      return {
        mb : c.style.marginBottom,
        pos: c.style.position,
        zi : c.style.zIndex,
        wc : c.style.willChange,
        to : c.style.transformOrigin,
      };
    });

    /* apply stacking styles */
    cards.forEach(function (card, i) {
      card.style.transformOrigin = 'top center';
      card.style.willChange      = 'transform';
      card.style.position        = 'relative';
      card.style.zIndex          = String(i + 1);
      if (i < cards.length - 1) {
        card.style.marginBottom = ITEM_DISTANCE + 'px';
      }
    });

    /* end sentinel — after the last card's parent row */
    var lastCard = cards[cards.length - 1];
    var endEl = document.createElement('div');
    endEl.setAttribute('aria-hidden', 'true');
    endEl.style.cssText = 'height:1px;pointer-events:none;';
    var row = lastCard.parentNode;
    if (row.nextSibling) row.parentNode.insertBefore(endEl, row.nextSibling);
    else row.parentNode.appendChild(endEl);

    var cardTops = []; // document-level top of each card (stable after measure)
    var stackPx  = 0;  // viewport-y where cards pin (= first card's natural top)
    var endTop   = 0;

    function measure() {
      /* reset transforms so we read natural layout positions */
      cards.forEach(function (c) { c.style.transform = ''; });

      var sy   = getScrollTop();
      cardTops = cards.map(function (c) {
        return c.getBoundingClientRect().top + sy;
      });
      endTop  = endEl.getBoundingClientRect().top + sy;

      /*
       * Pin zone = the first card's natural starting position.
       * This avoids an immediate jump at scroll=0 that would occur if we
       * used a fixed fraction of viewH that is larger than cardTops[0].
       */
      stackPx = cardTops[0] - sy; // viewport-y of card 0 at scroll=0
    }

    function update() {
      if (!cardTops.length) return;

      var scrollTop = getScrollTop();
      var viewH     = window.innerHeight;
      var pinEnd    = endTop - viewH * 0.5;

      for (var i = 0; i < cards.length; i++) {
        var ct       = cardTops[i];
        /*
         * pinStart: scroll position at which card i reaches the pin zone.
         *   natural viewport pos = ct - scrollTop
         *   pin zone for card i  = stackPx + ITEM_STACK_GAP * i
         *   pin when: ct - scrollTop == stackPx + ITEM_STACK_GAP * i
         *   => pinStart = ct - stackPx - ITEM_STACK_GAP * i
         */
        var pinStart = ct - stackPx - ITEM_STACK_GAP * i;

        var translateY    = 0;
        var scaleProgress = 0;

        if (scrollTop >= pinStart && scrollTop <= pinEnd) {
          /* keep card at its pin-zone viewport position */
          translateY    = scrollTop - ct + stackPx + ITEM_STACK_GAP * i;
          scaleProgress = Math.min(1, (scrollTop - pinStart) / SCALE_PX);
        } else if (scrollTop > pinEnd) {
          /* stack complete — hold at last pinned position */
          translateY    = pinEnd - ct + stackPx + ITEM_STACK_GAP * i;
          scaleProgress = 1;
        }
        /* else scrollTop < pinStart: card not yet pinned, translateY stays 0 */

        var targetScale = BASE_SCALE + i * ITEM_SCALE;
        var scale       = 1 - scaleProgress * (1 - targetScale);

        cards[i].style.transform =
          'translate3d(0,' + (Math.round(translateY * 10) / 10) + 'px,0)' +
          ' scale(' + (Math.round(scale * 1000) / 1000) + ')';
      }
    }

    function remeasure() {
      requestAnimationFrame(function () { measure(); update(); });
    }

    /* rAF polling loop — runs at ~60 fps regardless of scroll events.
       This is the most reliable fallback, especially for iOS Safari where
       'scroll' events don't fire during native momentum scrolling. */
    var rafId    = null;
    var lastScY  = -1;
    function rafTick() {
      rafId = requestAnimationFrame(rafTick);
      var sy = getScrollTop();
      if (sy !== lastScY) { lastScY = sy; update(); }
    }

    /* measure after layout settles from margin changes, then start loop */
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        measure();

        /* passive scroll listeners as primary signal */
        window.addEventListener('scroll',   update, { passive: true });
        document.addEventListener('scroll', update, { passive: true, capture: true });
        var appMain = document.querySelector('.app-main');
        if (appMain) appMain.addEventListener('scroll', update, { passive: true });

        /* touchmove fires every frame on iOS during momentum scroll */
        document.addEventListener('touchmove', update, { passive: true });

        window.addEventListener('resize', remeasure, { passive: true });

        /* start rAF polling as ultimate fallback */
        rafTick();
      });
    });

    return function destroy() {
      cancelAnimationFrame(rafId);
      window.removeEventListener('scroll',   update);
      document.removeEventListener('scroll', update, { capture: true });
      document.removeEventListener('touchmove', update);
      window.removeEventListener('resize',   remeasure);
      var m = document.querySelector('.app-main');
      if (m) m.removeEventListener('scroll', update);

      cards.forEach(function (card, i) {
        card.style.transform       = '';
        card.style.marginBottom    = snap[i].mb;
        card.style.position        = snap[i].pos;
        card.style.zIndex          = snap[i].zi;
        card.style.willChange      = snap[i].wc;
        card.style.transformOrigin = snap[i].to;
      });
      if (endEl.parentNode) endEl.parentNode.removeChild(endEl);
      cardTops = [];
    };
  }

  /* ── lifecycle ───────────────────────────────────────────────── */

  function check() {
    if (isMobile()) {
      if (!destroyFn) destroyFn = initStack();
    } else {
      if (destroyFn) { destroyFn(); destroyFn = null; }
    }
  }

  var prevMobile = null;
  function onResizeBreakpoint() {
    var m = isMobile();
    if (m !== prevMobile) {
      prevMobile = m;
      if (destroyFn) { destroyFn(); destroyFn = null; }
      check();
    }
  }

  function boot() {
    if (booted) return;
    booted     = true;
    prevMobile = isMobile();
    check();
    window.addEventListener('resize', onResizeBreakpoint, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})();
