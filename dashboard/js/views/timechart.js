// Records per month, as SVG bars plus a table of the same numbers. The SVG is hidden
// from screen readers; the table (inside <details>) is the accessible version.
//
// Clicking a month (a bar, or its row in the table) filters everything to that month;
// clicking it again shows every month. Like the ranked lists, the chart ignores its own
// filter: it always draws the whole period and greys the months outside the range.
(function (T) {
  "use strict";
  const { count, esc, formatDate, monthFull, monthLong, monthShort, niceStep, nounText } = T.format;
  const { countByMonth, filterItems, isFullRange, monthsInRange, pickMonth } = T.query;
  const { animateFrom } = T.motion;

  const HEIGHT = 220;
  const MARGIN = { t: 20, r: 8, b: 36, l: 36 };
  const MAX_BAR = 44;
  const MIN_LABEL_GAP = 40; // px between month labels

  function createTimeChart({ chart, table, sub, note, clear }, { store, data, tooltip }) {
    tooltip.bind(chart);
    const choose = (m) => { tooltip.hide(); store.set(pickMonth(data, store.get(), m)); };
    chart.addEventListener("click", (e) => {
      const hit = e.target.closest(".hit[data-m]");
      if (hit) choose(hit.dataset.m);
    });
    table.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-m]");
      if (b) choose(b.dataset.m);
    });
    clear.addEventListener("click", () => store.set({ from: data.months[0], to: data.months.at(-1) }));
    let last = null;
    let heights = {}; // month -> bar height last drawn, so bars rise or fall from there

    function draw() {
      if (!last) return;
      const { counts, months, from, to, full } = last;
      const W = Math.max(300, chart.clientWidth);
      const iw = W - MARGIN.l - MARGIN.r, ih = HEIGHT - MARGIN.t - MARGIN.b;
      const max = Math.max(1, ...Object.values(counts));
      const tick = niceStep(max / 4);
      const top = Math.ceil(max / tick) * tick;
      const y = (v) => MARGIN.t + ih - (v / top) * ih;
      const band = iw / months.length;
      const bw = Math.min(MAX_BAR, band * 0.62);
      const peak = months.reduce((a, b) => (counts[b] > counts[a] ? b : a), months[0]);
      // Label every k-th month, with k the smallest of 1/2/3/6/12 that leaves room for
      // the text. Labels sit on calendar boundaries (Jan, Apr, Jul...), so long ranges
      // read as quarters or years rather than arbitrary months.
      const every = [1, 2, 3, 6, 12].find((k) => band * k >= MIN_LABEL_GAP) || 12;
      const labelled = (m) => (Number(m.slice(5)) - 1) % every === 0;
      const firstLabel = months.find(labelled);

      let svg = "";
      for (let v = 0; v <= top; v += tick) {
        svg += `<line class="${v ? "grid" : "base"}" x1="${MARGIN.l}" x2="${W - MARGIN.r}" y1="${y(v)}" y2="${y(v)}"/>` +
          `<text class="tick" x="${MARGIN.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
      }
      months.forEach((m, i) => {
        const v = counts[m];
        const cx = MARGIN.l + band * (i + 0.5);
        const partial = data.partialMonth?.month === m;
        const out = !full && (m < from || m > to);
        const only = from === m && to === m;
        const tip = `<b>${monthLong(m)}</b>${partial ? ` (to ${formatDate(data.partialMonth.through)})` : ""}<br>${count(v)}` +
          `<br><span class="tip-hint">${only ? "Click to show every month" : "Click to show only this month"}</span>`;
        svg += `<rect class="hit" x="${MARGIN.l + band * i}" y="${MARGIN.t}" width="${band}" height="${ih}"
          data-m="${m}" data-tip="${esc(tip)}"/>`;
        svg += `<path class="bar${partial ? " partial" : ""}${out ? " out" : ""}" data-m="${m}" data-h="${MARGIN.t + ih - y(v)}" d="${roundedBar(cx - bw / 2, y(v), bw, MARGIN.t + ih - y(v))}"/>`;
        if (m === peak && v) svg += `<text class="label" x="${cx}" y="${y(v) - 6}" text-anchor="middle">${v}</text>`;
        if (labelled(m)) {
          const yearOnly = every === 12;
          svg += `<text class="tick" x="${cx}" y="${HEIGHT - MARGIN.b + 16}" text-anchor="middle">${yearOnly ? m.slice(0, 4) : monthShort(m)}</text>`;
          if (!yearOnly && (m === firstLabel || m.endsWith("-01"))) {
            svg += `<text class="tick" x="${cx}" y="${HEIGHT - MARGIN.b + 30}" text-anchor="middle">${m.slice(0, 4)}</text>`;
          }
        }
      });
      chart.innerHTML = `<svg viewBox="0 0 ${W} ${HEIGHT}" width="${W}" height="${HEIGHT}" aria-hidden="true" focusable="false">${svg}</svg>`;
      const bars = [...chart.querySelectorAll(".bar")];
      animateFrom(bars.filter((p) => Number(p.dataset.h) > 0 && heights[p.dataset.m] !== Number(p.dataset.h)).map((p) => ({
        el: p,
        from() { p.style.transform = `scaleY(${(heights[p.dataset.m] || 0) / Number(p.dataset.h)})`; },
        to() { p.style.transform = ""; },
      })));
      heights = Object.fromEntries(bars.map((p) => [p.dataset.m, Number(p.dataset.h)]));
    }

    if ("ResizeObserver" in window) {
      let width = 0;
      new ResizeObserver(() => { if (chart.clientWidth !== width) { width = chart.clientWidth; draw(); } }).observe(chart);
    }

    return {
      render({ state }) {
        const months = data.months;
        const dated = filterItems(data, state, { ignore: ["from", "to"] });
        const counts = countByMonth(dated, months);
        const full = isFullRange(data, state);
        last = { counts, months, from: state.from, to: state.to, full };
        draw();
        clear.hidden = full;

        table.innerHTML = `<caption class="visually-hidden">${nounText("{Many} per month")}. Choose a month to show only its ${nounText("{many}")}.</caption>
          <thead><tr><th scope="col">Month</th><th scope="col">${nounText("{Many}")}</th></tr></thead>
          <tbody>${months.map((m) => {
            const only = state.from === m && state.to === m;
            return `<tr><th scope="row"><button type="button" class="link-btn" data-m="${m}" aria-pressed="${only}">${monthFull(m)}</button></th><td>${counts[m]}</td></tr>`;
          }).join("")}</tbody>`;

        const scope = [state.state, state.cat && data.categoryLabel[state.cat], state.sector,
          state.q.trim() && `text matching “${state.q.trim()}”`].filter(Boolean);
        const shown = monthsInRange(data, state);
        const range = shown.length === 1 ? monthLong(shown[0]) : `${monthLong(shown[0])} to ${monthLong(shown.at(-1))}`;
        sub.textContent = `${scope.length ? scope.join(", ") : "All states and types"}, ` +
          `${monthLong(months[0])} to ${monthLong(months.at(-1))}. The busiest month is labelled. ` +
          (full ? `Click a month to show only its ${nounText("{many}")}.` : `Showing ${range}; other months are greyed out.`);

        const undated = dated.filter((it) => !it.month).length;
        const partial = data.partialMonth && months.includes(data.partialMonth.month)
          ? `${monthFull(data.partialMonth.month)} is incomplete: the data runs to ${formatDate(data.partialMonth.through)}, so its lighter bar is not a drop.`
          : "";
        const notes = [partial,
          undated && `${count(undated)} with only a year or no date ${undated === 1 ? "is" : "are"} not in this chart.`].filter(Boolean);
        note.hidden = !notes.length;
        note.textContent = notes.join(" ");
      },
    };
  }

  /** Bar path with 4px rounded top corners, anchored flat on the baseline. */
  function roundedBar(x, y, w, h) {
    if (h <= 0) return "";
    const r = Math.min(4, h, w / 2);
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }

  T.timechart = { createTimeChart };
})(window.Tracker = window.Tracker || {});
