// Shared motion helpers. Views re-render with innerHTML, so CSS transitions alone
// never run (every element is new). Instead a view records what it showed before,
// starts the new elements at those old values, and on the next frame lets go:
// the transitions in style.css then carry each mark to its new value.
// Everything here is skipped when the reader asks for reduced motion.
(function (T) {
  "use strict";
  const query = matchMedia("(prefers-reduced-motion: reduce)");
  const reduced = () => query.matches;

  /**
   * Start each element at its old state and release it on the next frame.
   * @param pairs  [{ el, from: (el) => void, to: (el) => void }]
   */
  function animateFrom(pairs) {
    if (reduced() || !pairs.length) return;
    for (const p of pairs) p.from(p.el);
    // Reading layout commits the starting values, so the release transitions.
    void pairs[0].el.getBoundingClientRect();
    requestAnimationFrame(() => { for (const p of pairs) p.to(p.el); });
  }

  T.motion = { reduced, animateFrom };
})(window.Tracker = window.Tracker || {});
