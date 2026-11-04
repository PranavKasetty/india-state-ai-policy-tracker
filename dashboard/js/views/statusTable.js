// Where each state stands: one row per state, four markers of AI policy
// (pipeline/profiles.py, carried in meta.profiles) and how much of its activity
// went beyond announcements (item stages). Each marker cites the developments it
// relies on; a cited development that passes the current filters links to its card
// below, otherwise to the publisher's report.
//
// The markers describe the state, not the filtered view, so filters do not change
// the rows; the chosen state is highlighted. Rows are ordered by how many markers
// are done, then announced, then by the number of actions taken.
(function (T) {
  "use strict";
  const { esc, stateSlug } = T.format;

  const LIMIT = 10;
  const COLUMNS = [
    ["ai_policy", "AI policy", { done: "Adopted", announced: "Announced" }],
    ["ai_body", "Dedicated AI body", { done: "Set up", announced: "Announced" }],
    ["funding", "State AI funding", { done: "Allocated", announced: "Announced" }],
    ["infrastructure", "AI infrastructure", { done: "Set up", announced: "Announced" }],
  ];

  function createStatusTable({ table, more, panel }, { store, data }, reveal) {
    const profiles = data.meta.profiles || {};
    if (!Object.keys(profiles).length) {
      panel.hidden = true;
      return { render() {} };
    }
    const byId = new Map(data.items.map((it) => [it.id, it]));
    const counts = {};
    for (const it of data.items) {
      const c = (counts[it.state] ||= { all: 0, action: 0, staged: 0 });
      c.all++;
      if (it.stage) c.staged++;
      if (it.stage === "decided" || it.stage === "underway") c.action++;
    }
    const score = (s) => COLUMNS.reduce((n, [f]) => n + ({ done: 10, announced: 1 }[profiles[s]?.[f]?.status] || 0), 0);
    const rows = data.meta.states.map((s) => s.name)
      .sort((a, b) => score(b) - score(a) || (counts[b]?.action || 0) - (counts[a]?.action || 0) || a.localeCompare(b));
    let showAll = false;

    table.addEventListener("click", (e) => {
      const a = e.target.closest("a.cite[data-id]");
      if (!a) return;
      e.preventDefault(); // following the #fragment would rewrite the filter hash
      reveal(a.dataset.id);
    });
    more.addEventListener("click", () => {
      showAll = !showAll;
      draw(store.get(), lastShown);
    });

    function cell(state, [field, name, words], shown) {
      const c = profiles[state]?.[field];
      if (!c || c.status === "none") return `<td class="st-none"><span class="visually-hidden">${esc(name)}: </span>None found</td>`;
      const cites = c.cites.filter((id) => byId.has(id)).map((id, i) => {
        const it = byId.get(id);
        return shown.has(id)
          ? `<a class="cite" href="#item-${esc(id)}" data-id="${esc(id)}" aria-label="Source ${i + 1}: ${esc(it.title)}, in the list below">${i + 1}</a>`
          : `<a class="cite" href="${esc(it.url)}" target="_blank" rel="noopener" aria-label="Source ${i + 1}: ${esc(it.title)}, ${esc(it.source)} (opens in a new tab)">${i + 1}</a>`;
      });
      return `<td><span class="st st-${esc(c.status)}">${esc(words[c.status])}</span> ${esc(c.text)}${
        cites.length ? ` <span class="cites">[${cites.join(", ")}]</span>` : ""}</td>`;
    }

    let lastShown = new Set();
    function draw(state, shown) {
      lastShown = shown;
      const visible = showAll ? rows : rows.slice(0, LIMIT);
      if (state.state && !visible.includes(state.state)) visible.push(state.state);
      table.innerHTML = `<thead><tr><th scope="col">State</th>${COLUMNS.map(([, name]) => `<th scope="col">${esc(name)}</th>`).join("")}
        <th scope="col">Action taken</th></tr></thead><tbody>${visible.map((s) => {
          const c = counts[s] || { all: 0, action: 0 };
          return `<tr${s === state.state ? ' class="is-chosen"' : ""}>
            <th scope="row"><a href="state/${esc(stateSlug(s))}/">${esc(s)}</a></th>
            ${COLUMNS.map((col) => cell(s, col, shown)).join("")}
            <td class="num">${c.all ? `${c.action} of ${c.all}` : "0"}</td></tr>`;
        }).join("")}</tbody>`;
      more.hidden = rows.length <= LIMIT;
      more.textContent = showAll ? `Show the first ${LIMIT} states` : `Show all ${rows.length} states`;
      more.setAttribute("aria-expanded", String(showAll));
    }

    return {
      render({ state, items }) {
        draw(state, new Set(items.map((it) => it.id)));
      },
    };
  }

  T.statusTable = { createStatusTable };
})(window.Tracker = window.Tracker || {});
