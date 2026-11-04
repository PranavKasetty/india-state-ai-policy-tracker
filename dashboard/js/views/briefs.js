// AI-written briefs (pipeline/briefs.py, carried in meta.briefs), shown above the
// list for the chosen state and/or type of activity, or the overall brief
// (meta.briefs.overall) when neither is chosen. A brief is a few sentences,
// each followed by the record IDs it relies on: "... [R1a2b3c4d, R5e6f7a8b]".
// Those IDs become numbered links. A cited development that passes the current
// filters links to its card below (itemsList.reveal pages to it); one filtered out
// links to the publisher's report instead.
//
// Each sentence becomes a point; the first is shown and the rest sit behind a
// "Show N more points" button, so the panel stays short above the list.
//
// A brief eases in when it changes (not on every re-render, such as a new sort
// order), and points revealed by the toggle fade in one after another.
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
    let showing = "";          // which briefs are on screen, to animate only on change
    const expanded = new Set(); // keys of briefs whose extra points are open

    box.addEventListener("click", (e) => {
      const toggle = e.target.closest("button.brief-toggle");
      if (toggle) {
        const open = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(open));
        expanded[open ? "add" : "delete"](toggle.dataset.key);
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

    function renderBrief(b, key, subject, shown, labelText) {
      const order = [];
      const num = (id) => (order.includes(id) ? order.indexOf(id) : order.push(id) - 1) + 1;
      // Brackets holding no valid ID (a garbled citation such as "[Ref58a154]") are dropped.
      const text = b.text.replace(/\s*\[(?![^\]]*R[0-9a-f]{8})[^\]]*\]/g, "");
      const points = text.trim().split(SENTENCE_END).map((sentence) => esc(sentence).replace(CITES_RE, (_, ids) => {
        const known = ids.split(/\s*,\s*/).filter((id) => shown.has(id) || byId.get(id)?.url);
        return known.length
          ? ` <span class="cites">[${known.map((id) => citation(id, num(id), shown)).join(", ")}]</span>`
          : "";
      }));
      const extra = points.length - SHOWN_POINTS;
      const more = `Show ${extra} more ${extra === 1 ? "point" : "points"}`;
      const open = expanded.has(key);
      const meta = [labelText, b.model,
        b.generated_at && formatDate(b.generated_at.slice(0, 10))].filter(Boolean).map(esc);
      return `<section class="brief" aria-labelledby="brief-${key}">
        <h3 id="brief-${key}">${esc(subject)}</h3>
        <p class="brief-label">${meta.join(" · ")}</p>
        <ul class="brief-points" id="brief-${key}-points">${points.map((p, i) =>
          i < SHOWN_POINTS ? `<li>${p}</li>`
            : `<li class="extra" style="--i:${i - SHOWN_POINTS}"${open ? "" : " hidden"}>${p}</li>`).join("")}</ul>
        ${extra > 0 ? `<button type="button" class="btn-quiet brief-toggle" aria-expanded="${open}"
          aria-controls="brief-${key}-points" data-key="${key}" data-more="${more}">${open ? "Show less" : more}</button>` : ""}
      </section>`;
    }

    return {
      render({ state, items }) {
        const below = nounText("AI-generated summary of the {many} below");
        const chosen = [];
        if (state.state) chosen.push([briefs.states[state.state], `state`, state.state, below]);
        if (state.cat) chosen.push([briefs.categories[state.cat], `cat`, `${label[state.cat] || state.cat}, across states`, below]);
        if (!state.state && !state.cat) {
          chosen.push([briefs.overall, "overall", "All states",
            nounText("AI-generated summary of the most-covered {many} in each state")]);
        }
        const found = chosen.filter(([b]) => b);
        box.hidden = !found.length;
        const now = found.map(([, key, subject]) => `${key}:${subject}`).join("|");
        if (now !== showing) expanded.clear();
        const changed = now !== showing && found.length > 0;
        showing = now;
        if (!found.length) { box.innerHTML = ""; return; }

        const shown = new Set(items.map((it) => it.id));
        const narrowed = state.sector || state.stage || state.focus || state.q || !isFullRange(data, state);
        box.innerHTML = found.map(([b, key, subject, text]) => renderBrief(b, key, subject, shown, text)).join("") +
          (narrowed ? `<p class="brief-note">${nounText("The summary covers all dates, sectors, stages and types of action, not only the {many} matching the current filters.")}</p>` : "") +
          `<p class="brief-note">Numbers mark the reports each sentence relies on. Check them before quoting.</p>`;
        if (changed && !T.motion.reduced()) {
          box.classList.remove("entering");
          void box.offsetWidth; // restart the animation
          box.classList.add("entering");
        }
      },
    };
  }

  T.briefs = { createBriefs };
})(window.Tracker = window.Tracker || {});
