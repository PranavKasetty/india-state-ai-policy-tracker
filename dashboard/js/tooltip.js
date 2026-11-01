// One shared tooltip. Any element with data-tip (HTML, already escaped) inside a
// bound root shows it on hover or keyboard focus. Tooltips only repeat values that
// are also on the page (cell text, the "Show the numbers" table), never gate them.
// Escape dismisses it (WCAG 1.4.13).
(function (T) {
  "use strict";
  function createTooltip(el) {
    const hide = () => { el.hidden = true; };

    function show(target, evt) {
      el.innerHTML = target.dataset.tip;
      el.hidden = false;
      const box = target.getBoundingClientRect();
      const fromPointer = evt && evt.clientX;
      let x = fromPointer ? evt.clientX + 14 : box.left;
      let y = fromPointer ? evt.clientY + 16 : box.bottom + 6;
      const { offsetWidth: w, offsetHeight: h } = el;
      if (x + w > innerWidth - 8) x = innerWidth - w - 8;
      if (y + h > innerHeight - 8) y = (fromPointer ? evt.clientY : box.top) - h - 10;
      el.style.left = `${Math.max(8, x)}px`;
      el.style.top = `${Math.max(8, y)}px`;
    }

    document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
    addEventListener("scroll", hide, { passive: true });

    return {
      bind(root) {
        root.addEventListener("pointermove", (e) => {
          const t = e.target.closest("[data-tip]");
          t ? show(t, e) : hide();
        });
        root.addEventListener("pointerleave", hide);
        root.addEventListener("focusin", (e) => { const t = e.target.closest("[data-tip]"); if (t) show(t); });
        root.addEventListener("focusout", hide);
      },
      hide,
    };
  }

  T.tooltip = { createTooltip };
})(window.Tracker = window.Tracker || {});
