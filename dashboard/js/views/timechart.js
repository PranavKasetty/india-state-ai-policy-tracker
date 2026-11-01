// Records per month, as SVG bars plus a table of the same numbers. The SVG is hidden
// from screen readers; the table (inside <details>) is the accessible version.
(function (T) {
  "use strict";
  const { count, esc, monthFull, monthLong, monthShort, niceStep, nounText } = T.format;
  const { countByMonth, monthsInRange } = T.query;

  const HEIGHT = 220;
  const MARGIN = { t: 20, r: 8, b: 36, l: 36 };
  const MAX_BAR = 44;
  const MIN_LABEL_GAP = 40; // px between month labels

  function createTimeChart({ chart, table, sub, note }, { data, tooltip }) {
    tooltip.bind(chart);
    let last = null;

    function draw() {
      if (!last) return;
      const { counts, months } = last;
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
        svg += `<rect class="hit" x="${MARGIN.l + band * i}" y="${MARGIN.t}" width="${band}" height="${ih}"
          data-tip="${esc(`<b>${monthLong(m)}</b><br>${count(v)}`)}"/>`;
        svg += `<path class="bar" d="${roundedBar(cx - bw / 2, y(v), bw, MARGIN.t + ih - y(v))}"/>`;
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
    }

    if ("ResizeObserver" in window) {
      let width = 0;
      new ResizeObserver(() => { if (chart.clientWidth !== width) { width = chart.clientWidth; draw(); } }).observe(chart);
    }

    return {
      render({ state, items }) {
        const months = monthsInRange(data, state);
        const counts = countByMonth(items, months);
        last = { counts, months };
        draw();

        table.innerHTML = `<caption class="visually-hidden">${nounText("{Many} per month")}</caption>
          <thead><tr><th scope="col">Month</th><th scope="col">${nounText("{Many}")}</th></tr></thead>
          <tbody>${months.map((m) => `<tr><th scope="row">${monthFull(m)}</th><td>${counts[m]}</td></tr>`).join("")}</tbody>`;

        const scope = [state.state, state.cat && data.categoryLabel[state.cat], state.sector,
          state.q.trim() && `text matching “${state.q.trim()}”`].filter(Boolean);
        sub.textContent = `${scope.length ? scope.join(", ") : "All states and types"}, ` +
          `${monthLong(months[0])} to ${monthLong(months.at(-1))}. The busiest month is labelled.`;

        const undated = items.filter((it) => !it.month).length;
        note.hidden = undated === 0;
        note.textContent = `${count(undated)} with only a year or no date ${undated === 1 ? "is" : "are"} not in this chart.`;
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
