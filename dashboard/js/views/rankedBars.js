// A ranked list of horizontal bars: developments per state, or per type of activity.
// Each row is a button that sets (or clears) that filter.
//
// Like the matrix, a list ignores its own filter so every row stays visible and the
// chosen one is highlighted; it does respect every other filter, so picking a state
// in one list re-ranks the types in the other.
(function (T) {
  "use strict";
  const { count, esc, formatNumber } = T.format;
  const { filterItems, rankBy } = T.query;

  const FILTER_KEY = { state: "state", cat: "cat" }; // dimension -> store key

  /**
   * @param list       <ol> to render into
   * @param dimension  "state" or "cat"
   */
  function createRankedBars({ list }, { store, data }, dimension) {
    const key = FILTER_KEY[dimension];

    list.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-id]");
      if (b) store.set({ [key]: store.get()[key] === b.dataset.id ? "" : b.dataset.id });
    });

    function render({ state }) {
      const rows = rankBy(filterItems(data, state, { ignore: [key] }), data, dimension);
      const max = Math.max(1, ...rows.map((r) => r.n));
      const chosen = state[key];

      const focusedId = list.contains(document.activeElement) ? document.activeElement.dataset.id : null;
      list.innerHTML = rows.map((r) => `<li>
        <button type="button" class="rank-row${r.n === 0 ? " is-zero" : ""}" data-id="${esc(r.id)}"${dimension === "cat" ? ` data-cat="${esc(r.id)}"` : ""}
          aria-pressed="${chosen === r.id}" aria-label="${esc(r.label)}: ${count(r.n)}">
          <span class="rank-label">${esc(r.label)}</span>
          <span class="rank-track" aria-hidden="true"><span class="rank-bar" style="width:${(100 * r.n / max).toFixed(1)}%"></span></span>
          <span class="rank-value" aria-hidden="true">${formatNumber(r.n)}</span>
        </button></li>`).join("");
      list.classList.toggle("has-choice", Boolean(chosen));
      if (focusedId) list.querySelector(`button[data-id="${CSS.escape(focusedId)}"]`)?.focus({ preventScroll: true });
    }

    return { render };
  }

  T.rankedBars = { createRankedBars };
})(window.Tracker = window.Tracker || {});
