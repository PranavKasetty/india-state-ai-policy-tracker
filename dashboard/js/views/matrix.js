// State x activity-type matrix: the detail view, in a collapsed section below the chart.
//
// It ignores the state and type filters so all rows and columns stay visible; the
// chosen state/type is highlighted instead. Clicking a state, type or cell sets
// those filters. Every cell shows its value as text, so colour is never the only cue.
(function (T) {
  "use strict";
  const { count, esc, niceStep, nounText } = T.format;
  const { filterItems, stateByCategory } = T.query;

  const STEPS = 7; // ramp steps --s1..--s7 in tokens.css; --s0 is zero

  const MODES = {
    count: {
      value: (row, cat) => row.byCategory[cat],
      text: (v) => String(v),
      scaleLabel: nounText("{Many}"),
      sub: nounText("Each cell counts a state's {many} of that type. One {one} can have several types."),
    },
    share: {
      value: (row, cat) => (row.total ? (100 * row.byCategory[cat]) / row.total : 0),
      text: (v, row) => (row.total ? `${Math.round(v)}%` : "–"),
      scaleLabel: nounText("Share of the state's {many} (%)"),
      sub: nounText("Each cell is the share of a state's {many} of that type. One {one} can have several types, so a row can add up to more than 100%."),
    },
  };

  function createMatrix({ table, scale, sub, modeGroup }, { store, data, tooltip }) {
    const cats = data.meta.categories;
    const label = data.categoryLabel;
    tooltip.bind(table);

    table.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      const s = store.get();
      const { state, cat } = b.dataset;
      if (state && cat) {
        const same = s.state === state && s.cat === cat;
        store.set({ state: same ? "" : state, cat: same ? "" : cat });
      } else if (state) store.set({ state: s.state === state ? "" : state });
      else if (cat) store.set({ cat: s.cat === cat ? "" : cat });
    });
    modeGroup.addEventListener("click", (e) => {
      const b = e.target.closest("[data-mode]");
      if (b) store.set({ view: b.dataset.mode });
    });

    function render({ state }) {
      const mode = MODES[state.view] || MODES.count;
      const rows = stateByCategory(filterItems(data, state, { ignore: ["state", "cat"] }), data, []);

      const maxValue = Math.max(1, ...rows.flatMap((r) => cats.map((c) => mode.value(r, c.id))));
      const step = niceStep(maxValue / STEPS);
      const bin = (v) => (v <= 0 ? 0 : Math.min(STEPS, Math.ceil(v / step)));
      const head = `<caption class="visually-hidden">${nounText("{Many} by state and type of activity. Rows are states, sorted by total {many}.")}</caption>
        <thead><tr><th scope="col"><span class="visually-hidden">State</span></th>${cats.map((c) => `<th scope="col">${axisButton({ cat: c.id }, label[c.id], state.cat === c.id)}</th>`).join("")}
        <th scope="col" class="num">Total</th></tr></thead>`;

      const body = rows.map((r) => {
        const cells = cats.map((c) => {
          const n = r.byCategory[c.id];
          const v = mode.value(r, c.id);
          const b = bin(v);
          const pct = r.total ? Math.round((100 * n) / r.total) : 0;
          const picked = state.state === r.state && state.cat === c.id;
          const tip = `<b>${esc(r.state)}, ${esc(label[c.id])}</b><br>${count(n)}, ${pct}% of the state's ${r.total}`;
          return `<td class="cell"><button type="button" class="cell-btn${state.cat === c.id ? " in-focus" : ""}"
            style="--bg:var(--s${b});--fg:var(--s${b}-ink)" data-state="${esc(r.state)}" data-cat="${c.id}"
            data-tip="${esc(tip)}" aria-pressed="${picked}"
            aria-label="${esc(label[c.id])}: ${count(n)}${state.view === "share" ? `, ${pct}%` : ""}">${mode.text(v, r)}</button></td>`;
        }).join("");
        return `<tr class="${state.state === r.state ? "in-focus" : ""}">
          <th scope="row">${axisButton({ state: r.state }, r.state, state.state === r.state)}</th>${cells}
          <td class="total">${r.total}</td></tr>`;
      }).join("");

      // Re-rendering replaces the buttons, so put keyboard focus back where it was.
      const focused = table.contains(document.activeElement) ? { ...document.activeElement.dataset } : null;
      // Each cell's previous colour, so fills fade to their new step instead of jumping.
      const key = (b) => `${b.dataset.state}|${b.dataset.cat}`;
      const oldFill = new Map([...table.querySelectorAll(".cell-btn")].map((b) => [key(b), getComputedStyle(b).backgroundColor]));
      table.innerHTML = head + `<tbody>${body}</tbody>`;
      table.classList.toggle("has-focus", Boolean(state.state || state.cat));
      T.motion.animateFrom([...table.querySelectorAll(".cell-btn")].filter((b) => oldFill.has(key(b))).map((b) => ({
        el: b,
        from() { b.style.backgroundColor = oldFill.get(key(b)); },
        to() { b.style.backgroundColor = ""; },
      })));
      if (focused) restoreFocus(table, focused);

      sub.textContent = `${mode.sub} Select a state, type or cell to filter the page.`;
      scale.innerHTML = scaleLegend(mode, step);
      modeGroup.querySelectorAll("[data-mode]").forEach((b) =>
        b.setAttribute("aria-pressed", String(b.dataset.mode === (state.view || "count"))));
    }

    return { render };
  }

  function axisButton(data, text, pressed) {
    const attrs = Object.entries(data).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");
    return `<button type="button" class="axis-btn" ${attrs} aria-pressed="${pressed}">${esc(text)}</button>`;
  }

  function restoreFocus(table, { state, cat }) {
    const sel = [state && `[data-state="${CSS.escape(state)}"]`, cat && `[data-cat="${CSS.escape(cat)}"]`].filter(Boolean).join("");
    const candidates = [...table.querySelectorAll(`button${sel}`)];
    // Prefer the exact kind of button (axis vs cell) that had focus.
    const el = candidates.find((b) => Boolean(b.dataset.state) === Boolean(state) && Boolean(b.dataset.cat) === Boolean(cat));
    if (el) el.focus({ preventScroll: true });
  }

  function scaleLegend(mode, step) {
    const fmt = (x) => (Number.isInteger(x) ? x : x.toFixed(1));
    const steps = Array.from({ length: STEPS + 1 }, (_, i) => {
      const text = i === 0 ? "0" : `${fmt((i - 1) * step)}–${fmt(i * step)}`;
      return `<li><span class="sw" style="background:var(--s${i})"></span>${text}</li>`;
    }).join("");
    return `<span>${mode.scaleLabel}</span><ol aria-label="Colour scale">${steps}</ol>`;
  }

  T.matrix = { createMatrix };
})(window.Tracker = window.Tracker || {});
