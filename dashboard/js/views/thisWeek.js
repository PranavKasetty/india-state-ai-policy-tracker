// This week: what returning visitors come for. The developments reported in the 7
// days up to the latest data, the most covered first, and the busiest states, with
// a link to follow new ones by email or feed. It follows the state filter (a chosen
// state shows its own week) and ignores the others, so it always answers "what's new".
(function (T) {
  "use strict";
  const { esc, formatDate, formatNumber, plural, stateSlug } = T.format;
  const { outlets } = T.query;

  const DAYS = 7;
  const SHOW = 6;
  const BUSIEST = 5;

  function createThisWeek({ panel, sub, list, states, follow }, { store, data }, reveal) {
    const end = data.meta.period_end;
    if (!end) {
      panel.hidden = true;
      return { render() {} };
    }
    const from = new Date(Date.parse(end) - (DAYS - 1) * 864e5).toISOString().slice(0, 10);
    const week = data.items.filter((it) => it.date && it.date >= from && it.date <= end);
    const stageLabel = Object.fromEntries((data.meta.stages || []).map((s) => [s.id, s.label]));

    // A headline opens its card when the filters show it, else the publisher's report.
    list.addEventListener("click", (e) => {
      const a = e.target.closest("a[data-id]");
      if (a && reveal(a.dataset.id)) e.preventDefault();
    });
    states.addEventListener("click", (e) => {
      const b = e.target.closest("[data-state]");
      if (b) store.set({ state: b.dataset.state });
    });

    return {
      render({ state }) {
        const chosen = state.state;
        const mine = chosen ? week.filter((it) => it.state === chosen) : week;
        const where = chosen ? ` in ${esc(chosen)}` : "";
        sub.innerHTML = mine.length
          ? `${formatNumber(mine.length)} ${mine.length === 1 ? "development" : "developments"} reported${where} from ${formatDate(from)} to ${formatDate(end)}, the most covered first.`
          : `Nothing reported${where} from ${formatDate(from)} to ${formatDate(end)}.`;
        follow.href = `updates/${chosen ? `#${stateSlug(chosen)}` : ""}`;
        follow.textContent = chosen ? `Get ${chosen}'s new developments by email or feed` : "Get new developments by email or feed";

        const top = [...mine].sort((a, b) => outlets(b) - outlets(a) || b.date.localeCompare(a.date)).slice(0, SHOW);
        list.innerHTML = top.map((it) => {
          const n = outlets(it);
          const bits = [chosen ? "" : esc(it.state), stageLabel[it.stage] ? esc(stageLabel[it.stage]) : "",
            n > 1 ? `${n} outlets` : ""].filter(Boolean).join(", ");
          return `<li><a href="${esc(it.url)}" data-id="${esc(it.id)}" target="_blank" rel="noopener">${esc(it.title)}</a>
            <span class="week-meta">${bits}</span></li>`;
        }).join("");
        list.hidden = !top.length;

        if (chosen) {
          states.hidden = true;
          return;
        }
        const counts = {};
        for (const it of week) counts[it.state] = (counts[it.state] || 0) + 1;
        const busiest = Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, BUSIEST);
        states.hidden = !busiest.length;
        states.innerHTML = `Busiest this week: ${busiest.map(([s, n]) =>
          `<button type="button" class="link-btn" data-state="${esc(s)}">${esc(s)}</button> ${n}`).join(", ")}
          <span class="week-of">(of ${plural(Object.keys(counts).length, "state")} with news)</span>`;
      },
    };
  }

  T.thisWeek = { createThisWeek };
})(window.Tracker = window.Tracker || {});
