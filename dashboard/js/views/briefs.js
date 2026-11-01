// AI-written briefs (pipeline/briefs.py, carried in meta.briefs), shown above the
// list for the chosen state and/or type of activity. A brief is a few sentences,
// each followed by the record IDs it relies on: "... [R1a2b3c4d, R5e6f7a8b]".
// Those IDs become numbered links. A cited development that passes the current
// filters links to its card below (itemsList.reveal pages to it); one filtered out
// links to the publisher's report instead.
//
// Each sentence becomes a point; the first is shown and the rest sit behind a
// "Show N more points" button, so the panel stays short above the list.
//
// Briefs are written from all of a group's developments, so they do not follow the
// date, sector or search filters; a note says so when any of those is set.
(function (T) {
  "use strict";
  const { esc, formatDate, nounText } = T.format;
  const { isFullRange } = T.query;

  const CITES_RE = /\s*\[\s*(R[0-9a-f]{8}(?:\s*,\s*R[0-9a-f]{8})*)\s*\]/g;
  // Sentence ends: after . ! or ? (and any citation bracket that follows), before a capital.
  const SENTENCE_END = /(?<=[.!?](?:\s*\[[^\]]*\])?)\s+(?=[A-Z"“‘(])/;
  const SHOWN_POINTS = 1;

  /**
   * @param box     element the briefs render into
   * @param reveal  (id) => scroll to and focus that development's card
   */
  function createBriefs({ box }, { data }, reveal) {
    const briefs = { states: {}, categories: {}, ...(data.meta.briefs || {}) };
    const byId = new Map(data.items.map((it) => [it.id, it]));
    const label = data.categoryLabel;

    box.addEventListener("click", (e) => {
      const toggle = e.target.closest("button.brief-toggle");
      if (toggle) {
        const open = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(open));
        document.getElementById(toggle.getAttribute("aria-controls"))
          .querySelectorAll(".extra").forEach((li) => { li.hidden = !open; });
        toggle.textContent = open ? "Show less" : toggle.dataset.more;
        return;
      }
      const a = e.target.closest("a.cite[data-id]");
      if (!a) return;
      e.preventDefault(); // following the #fragment would rewrite the filter hash
      reveal(a.dataset.id);
    });

    function citation(id, n, shown) {
      const it = byId.get(id);
      if (shown.has(id)) {
        return `<a class="cite" href="#item-${esc(id)}" data-id="${esc(id)}"
          aria-label="Source ${n}: ${esc(it.title)}, in the list below">${n}</a>`;
      }
      return `<a class="cite" href="${esc(it.url)}" target="_blank" rel="noopener"
        aria-label="Source ${n}: ${esc(it.title)}, ${esc(it.source)} (opens in a new tab)">${n}</a>`;
    }

    function renderBrief(b, key, subject, shown) {
      const order = [];
      const num = (id) => (order.includes(id) ? order.indexOf(id) : order.push(id) - 1) + 1;
      const points = b.text.trim().split(SENTENCE_END).map((sentence) => esc(sentence).replace(CITES_RE, (_, ids) => {
        const known = ids.split(/\s*,\s*/).filter((id) => shown.has(id) || byId.get(id)?.url);
        return known.length
          ? ` <span class="cites">[${known.map((id) => citation(id, num(id), shown)).join(", ")}]</span>`
          : "";
      }));
      const extra = points.length - SHOWN_POINTS;
      const more = `Show ${extra} more ${extra === 1 ? "point" : "points"}`;
      const meta = [nounText("AI-generated summary of the {many} below"), b.model,
        b.generated_at && formatDate(b.generated_at.slice(0, 10))].filter(Boolean).map(esc);
      return `<section class="brief" aria-labelledby="brief-${key}">
        <h3 id="brief-${key}">${esc(subject)}</h3>
        <p class="brief-label">${meta.join(" · ")}</p>
        <ul class="brief-points" id="brief-${key}-points">${points.map((p, i) =>
          `<li${i >= SHOWN_POINTS ? ` class="extra" hidden` : ""}>${p}</li>`).join("")}</ul>
        ${extra > 0 ? `<button type="button" class="btn-quiet brief-toggle" aria-expanded="false"
          aria-controls="brief-${key}-points" data-more="${more}">${more}</button>` : ""}
      </section>`;
    }

    return {
      render({ state, items }) {
        const chosen = [];
        if (state.state) chosen.push([briefs.states[state.state], "state", state.state]);
        if (state.cat) chosen.push([briefs.categories[state.cat], "cat", `${label[state.cat] || state.cat}, across states`]);
        const found = chosen.filter(([b]) => b);
        box.hidden = !found.length;
        if (!found.length) { box.innerHTML = ""; return; }

        const shown = new Set(items.map((it) => it.id));
        const narrowed = state.sector || state.q || !isFullRange(data, state);
        box.innerHTML = found.map(([b, key, subject]) => renderBrief(b, key, subject, shown)).join("") +
          (narrowed ? `<p class="brief-note">${nounText("The summary covers all dates and sectors, not only the {many} matching the current filters.")}</p>` : "") +
          `<p class="brief-note">Numbers mark the reports each sentence relies on. Check them before quoting.</p>`;
      },
    };
  }

  T.briefs = { createBriefs };
})(window.Tracker = window.Tracker || {});
