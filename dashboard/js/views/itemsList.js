// The developments matching every filter, paged, with thumbnails, in one of three
// orders (query.sortItems): newest, most covered (outlet count), or trending
// (outlet count decayed by age, computed in the browser so it stays current
// between data refreshes).
//
// Thumbnails are the publisher's og:image, hotlinked (pipeline/enrich.py). Many
// publishers block hotlinking or the image disappears, so every thumbnail sits
// on a fallback tile showing the state code: if the image is missing or fails to
// load, the tile is what remains. Images are decorative (alt=""); the headline
// carries the meaning.
(function (T) {
  "use strict";
  const { esc, formatDate, formatNumber, monthLong, nounText, plural } = T.format;
  const { outlets, sortItems } = T.query;

  const PAGE_SIZE = 25;
  const MAX_NAMED = 4; // outlets named inline; more go in a "List all" disclosure
  const LIST = new Intl.ListFormat("en-IN", { style: "long", type: "conjunction" });
  const SORT_NOTES = {
    newest: "Newest first.",
    covered: "Most covered first: reported by the most outlets.",
    trending: "Trending first: widely covered and recent. More outlets and fewer days old rank higher.",
  };
  const DEDUPE_NOTE = nounText(" When several outlets covered the same {one}, the earliest report is shown.");

  function createItemsList({ list, empty, more, sortGroup, sub }, { store, data }) {
    const label = data.categoryLabel;
    const code = Object.fromEntries(data.meta.states.map((s) => [s.name, s.code || s.name.slice(0, 2)]));
    let items = [];
    let shown = PAGE_SIZE;

    sortGroup.addEventListener("click", (e) => {
      const b = e.target.closest("[data-sort]");
      if (b) store.set({ sort: b.dataset.sort });
    });

    // Image errors do not bubble, so listen in the capture phase.
    list.addEventListener("error", (e) => {
      if (e.target.tagName === "IMG") e.target.remove();
    }, true);

    function item(it) {
      const title = it.url
        ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.title)}<span class="visually-hidden"> (opens in a new tab)</span></a>`
        : esc(it.title);
      const img = it.image
        ? `<img src="${esc(it.image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">`
        : "";
      // Name every outlet in visible text (a hover-only title is unreachable by
      // keyboard and touch). Long lists sit behind a native disclosure.
      const all = [it.source, ...it.alsoReportedBy];
      const reportedBy = all.length <= MAX_NAMED
        ? esc(LIST.format(all))
        : `${esc(it.source)} and ${plural(all.length - 1, "other outlet")}`;
      const outletList = all.length > MAX_NAMED
        ? `<details class="outlets"><summary>List all ${all.length} outlets</summary><p>${esc(LIST.format(all))}.</p></details>`
        : "";
      const n = outlets(it);
      const coverage = n > 1 ? `<li class="coverage">${n} outlets</li>` : "";
      const tags = it.tags.map((t) => `<li class="tag${t === it.category ? " primary" : ""}" data-cat="${esc(t)}">${esc(label[t] || t)}</li>`).join("");
      return `<li class="item" id="item-${esc(it.id)}">
        <div class="thumb" aria-hidden="true"><span class="thumb-code">${esc(code[it.state] || "")}</span>${img}</div>
        <div class="item-body">
          <h3 class="item-title">${title}</h3>
          ${it.summary ? `<p class="item-summary">${esc(it.summary)}</p>` : ""}
          <p class="item-meta">${itemDate(it)}, ${esc(it.state)}. Reported by ${reportedBy}.</p>
          ${outletList}
          <ul class="item-tags" aria-label="Coverage, types and sector">${coverage}${tags}<li class="sector">${esc(it.sector)}</li></ul>
        </div></li>`;
    }

    function draw(focusFrom = -1) {
      list.innerHTML = items.slice(0, shown).map(item).join("");
      empty.hidden = items.length > 0;
      const left = items.length - shown;
      more.hidden = left <= 0;
      more.textContent = `Show ${Math.min(PAGE_SIZE, left)} more (${formatNumber(left)} not shown)`;
      // After "Show more", move focus to the first new item so keyboard and screen
      // reader users continue from there instead of jumping back to the top.
      if (focusFrom >= 0) {
        const heading = list.children[focusFrom]?.querySelector(".item-title");
        if (heading) { heading.tabIndex = -1; heading.focus(); }
      }
    }

    more.addEventListener("click", () => {
      const from = shown;
      shown += PAGE_SIZE;
      draw(from);
    });

    /** Show the card for `id` (paging to it if needed), scroll to it and focus its headline. */
    function reveal(id) {
      const at = items.findIndex((it) => it.id === id);
      if (at < 0) return false;
      if (at >= shown) {
        shown = Math.ceil((at + 1) / PAGE_SIZE) * PAGE_SIZE;
        draw();
      }
      const heading = list.children[at].querySelector(".item-title");
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
      heading.scrollIntoView({ block: "start" }); // instant: a long smooth glide only delays the reader
      return true;
    }

    return {
      reveal,
      render(ctx) {
        const mode = ctx.state.sort;
        items = sortItems(ctx.items, mode);
        sortGroup.querySelectorAll("[data-sort]").forEach((b) =>
          b.setAttribute("aria-pressed", String(b.dataset.sort === mode)));
        sub.textContent = (SORT_NOTES[mode] || SORT_NOTES.newest) + DEDUPE_NOTE;
        shown = PAGE_SIZE;
        draw();
      },
    };
  }

  function itemDate(it) {
    if (it.precision === "day") return `<time datetime="${it.date}">${formatDate(it.date)}</time>`;
    if (it.precision === "month" && it.month) return `<time datetime="${it.month}">${monthLong(it.month)}</time>`;
    if (it.date) return `<time datetime="${esc(it.date.slice(0, 4))}">${esc(it.date.slice(0, 4))}</time>`;
    return "Date unknown";
  }

  T.itemsList = { createItemsList };
})(window.Tracker = window.Tracker || {});
