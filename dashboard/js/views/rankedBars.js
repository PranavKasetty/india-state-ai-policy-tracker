// A ranked list of horizontal bars: developments per state, or per type of activity.
// Each row is a button that sets (or clears) that filter.
//
// Like the matrix, a list ignores its own filter so every row stays visible and the
// chosen one is highlighted; it does respect every other filter, so picking a state
// in one list re-ranks the types in the other.
//
// A long list (all 28 states) shows its top `limit` rows plus the chosen one, with a
// button to show the rest, so the panel stays level with its neighbour.
(function (T) {
  "use strict";
  const { count, esc, formatNumber } = T.format;
  const { filterItems, rankBy } = T.query;
  const { animateFrom } = T.motion;

  const FILTER_KEY = { state: "state", cat: "cat" }; // dimension -> store key

  /**
   * @param list       <ol> to render into
   * @param more       optional "Show all" button, used when rows exceed `limit`
   * @param dimension  "state" or "cat"
   * @param limit      rows shown before "Show all" (Infinity: always all)
   */
  function createRankedBars({ list, more }, { store, data }, dimension, { limit = Infinity, noun = "rows" } = {}) {
    const key = FILTER_KEY[dimension];
    let expanded = false;
    let last = null;

    more?.addEventListener("click", () => {
      expanded = !expanded;
      if (last) render(last);
    });

    list.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-id]");
      if (b) store.set({ [key]: store.get()[key] === b.dataset.id ? "" : b.dataset.id });
    });

    function render(ctx) {
      last = ctx;
      const { state } = ctx;
      const all = rankBy(filterItems(data, state, { ignore: [key] }), data, dimension);
      const max = Math.max(1, ...all.map((r) => r.n));
      const chosen = state[key];
      // Collapse only when it hides enough to matter (more than 2 rows).
      const collapsible = more && all.length > limit + 2;
      const rows = collapsible && !expanded ? all.filter((r, i) => i < limit || r.id === chosen) : all;
      if (more) {
        more.hidden = !collapsible;
        more.setAttribute("aria-expanded", String(expanded));
        more.textContent = expanded ? `Show the top ${limit} only` : `Show all ${all.length} ${noun}`;
      }

      const focusedId = list.contains(document.activeElement) ? document.activeElement.dataset.id : null;
      // Where each row and bar was, so the new ones can move and grow from there
      // (first render: bars grow from zero).
      const before = new Map([...list.querySelectorAll("button[data-id]")].map((b) =>
        [b.dataset.id, { top: b.getBoundingClientRect().top, width: b.querySelector(".rank-bar").style.width }]));
      list.innerHTML = rows.map((r) => `<li>
        <button type="button" class="rank-row${r.n === 0 ? " is-zero" : ""}" data-id="${esc(r.id)}"${dimension === "cat" ? ` data-cat="${esc(r.id)}"` : ""}
          aria-pressed="${chosen === r.id}" aria-label="${esc(r.label)}: ${count(r.n)}">
          <span class="rank-label">${esc(r.label)}</span>
          <span class="rank-track" aria-hidden="true"><span class="rank-bar" style="width:${(100 * r.n / max).toFixed(1)}%"></span></span>
          <span class="rank-value" aria-hidden="true">${formatNumber(r.n)}</span>
        </button></li>`).join("");
      list.classList.toggle("has-choice", Boolean(chosen));
      animateFrom([...list.querySelectorAll("button[data-id]")].map((b) => {
        const bar = b.querySelector(".rank-bar");
        const width = bar.style.width;
        const old = before.get(b.dataset.id);
        return {
          el: b,
          from() {
            bar.style.width = old ? old.width : "0%";
            const dy = old ? old.top - b.getBoundingClientRect().top : 0;
            if (dy) b.style.transform = `translateY(${dy}px)`;
          },
          to() { bar.style.width = width; b.style.transform = ""; },
        };
      }));
      if (focusedId) list.querySelector(`button[data-id="${CSS.escape(focusedId)}"]`)?.focus({ preventScroll: true });
    }

    return { render };
  }

  T.rankedBars = { createRankedBars };
})(window.Tracker = window.Tracker || {});
