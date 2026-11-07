// Entry point: load the data, create the store, wire up the views.
//
// Scripts are classic (not ES modules) so the page also works opened from disk.
// Each file adds its functions to window.Tracker; index.html loads them in order.
//
// To add a view: write js/views/<name>.js that sets T.<name> = { create<Name> },
// where create<Name>(elements, deps) returns { render(ctx) }. Add its markup and
// <script> tag (before main.js) to index.html, and register it in
// `views` below. ctx is { state, data, items } where items already pass every filter.
(function (T) {
  "use strict";
  const { loadDataset } = T.dataset;
  const { count, formatDate, formatNumber, issueUrl, monthLong, nounText } = T.format;
  const { defaultFilters, filterItems, FOCUS_VALUES, STAGE_VALUES, SORT_MODES } = T.query;
  const { createStore, readHash, writeHash } = T.store;
  const { initTheme } = T.theme;
  const { createTooltip } = T.tooltip;
  const { createFilters } = T.filters;
  const { createItemsList } = T.itemsList;
  const { createMatrix } = T.matrix;
  const { createRankedBars } = T.rankedBars;
  const { createTimeChart } = T.timechart;
  const { createBriefs } = T.briefs;
  const download = T.download;
  const { createStatusTable } = T.statusTable;
  const { createThisWeek } = T.thisWeek;

  const $ = (id) => document.getElementById(id);

  function main() {
    initTheme($("theme-toggle"));

    let data;
    try {
      data = loadDataset();
    } catch (err) {
      showError(err);
      return;
    }

    const defaults = { ...defaultFilters(data), view: "count", sort: "newest" };
    const allowed = {
      state: data.meta.states.map((s) => s.name),
      cat: data.meta.categories.map((c) => c.id),
      sector: data.meta.sectors,
      focus: FOCUS_VALUES,
      stage: STAGE_VALUES,
      from: data.months,
      to: data.months,
      view: ["count", "share"],
      sort: SORT_MODES,
    };
    // A shared entry link (#item=R...) opens the full list on that entry.
    const linkedItem = () => new URLSearchParams(location.hash.slice(1)).get("item");
    const openItem = linkedItem();
    const store = createStore({ ...defaults, ...readHash(defaults, allowed) });
    const tooltip = createTooltip($("tooltip"));
    const deps = { store, data, tooltip, defaults };

    const itemsList = createItemsList({ list: $("items-list"), empty: $("items-empty"), more: $("items-more"), sortGroup: $("items-sort"), sub: $("items-sub") }, deps);
    const views = [
      createFilters($("filters"), deps),
      createThisWeek({ panel: $("week-panel"), sub: $("week-sub"), list: $("week-list"), states: $("week-states"), follow: $("week-follow") }, deps, itemsList.reveal),
      createStatusTable({ table: $("status-table"), more: $("status-more"), panel: $("status-panel"), jump: $("status-jump") }, deps, itemsList.reveal),
      createRankedBars({ list: $("state-bars"), more: $("state-more") }, deps, "state", { limit: 12, noun: "states" }),
      createRankedBars({ list: $("type-bars") }, deps, "cat"),
      createMatrix({ table: $("matrix"), scale: $("matrix-scale"), sub: $("matrix-sub"), modeGroup: $("matrix-mode") }, deps),
      createTimeChart({ chart: $("timechart"), table: $("time-table"), sub: $("time-sub"), note: $("time-note"), clear: $("time-all") }, deps),
      createBriefs({ box: $("briefs") }, deps, itemsList.reveal),
      itemsList,
    ];

    renderStatic(data);
    initDisclosures();
    // The hash holds the filters, so a plain #fragment link would clear them.
    $("to-list").addEventListener("click", () => {
      const heading = $("items-title");
      heading.scrollIntoView({ block: "start" });
      heading.focus({ preventScroll: true });
    });
    $("download-csv").addEventListener("click", () => {
      const state = store.get();
      download.save(filterItems(data, state), data, state);
    });
    // Names the types in query.POLICY_TYPES; keep the two in step.
    const policyNote = " Policy and governance only: strategies and policies, regulation, governance bodies, funding and partnerships (MoUs).";
    const stageNotes = {
      action: " Action taken: approved, signed, launched or in use, not just announced.",
      announced: " Announced or planned: intentions, proposals and statements, not yet approved or launched.",
    };
    const render = (state) => {
      const items = filterItems(data, state);
      $("result-count").textContent = (items.length === data.items.length
        ? `Showing all ${count(items.length)}.`
        : `Showing ${formatNumber(items.length)} of ${count(data.items.length)}.`) +
        (state.focus === "policy" ? policyNote : "") + (stageNotes[state.stage] || "");
      for (const view of views) view.render({ state, data, items });
      writeHash(state, defaults);
    };
    store.subscribe(render);
    store.subscribe(countFilterChoices(store.get()));
    render(store.get());
    if (openItem) itemsList.reveal(openItem);

    addEventListener("hashchange", () => {
      const id = linkedItem();
      store.set({ ...defaults, ...readHash(defaults, allowed) });
      if (id) itemsList.reveal(id);
    });
  }

  function renderStatic(data) {
    const { meta, months } = data;
    for (const el of document.querySelectorAll("[data-noun]")) {
      const text = nounText(el.dataset.noun);
      if (el.hasAttribute("aria-label")) el.setAttribute("aria-label", text); else el.textContent = text;
    }
    $("mock-banner").hidden = !meta.is_mock;
    $("suggest-link").href = issueUrl("Missing development: ",
      ["State:", "What happened:", "Link to a news report or government source:", ""].join("\n"));
    $("lede").textContent = `AI-related activity by ${meta.states.length} state governments, as reported in the news` +
      (months.length ? `, ${monthLong(months[0])} to ${monthLong(months.at(-1))}.` : ".");
    $("generated").textContent = meta.generated_at
      ? `${meta.is_mock ? "Mock data generated" : "Data last updated"} ${formatDate(meta.generated_at.slice(0, 10))}.`
      : "";
    updateDatasetLd(meta, months);
  }

  /** Put the covered period and last update into the page's schema.org Dataset. */
  function updateDatasetLd(meta, months) {
    const el = $("dataset-ld");
    if (!el) return;
    try {
      const ld = JSON.parse(el.textContent);
      if (months.length) ld.temporalCoverage = `${months[0]}/${months.at(-1)}`;
      if (meta.generated_at) ld.dateModified = meta.generated_at;
      el.textContent = JSON.stringify(ld);
    } catch (err) {
      console.warn("Could not update the dataset description", err);
    }
  }

  /**
   * Count which state, type, sector, stage and policy filter readers choose, as GoatCounter
   * events (e.g. "filter/state/Kerala"). Search text is never sent. Does nothing when
   * the counter has not loaded (blocked, offline or opened from disk).
   */
  function countFilterChoices(initial) {
    let prev = initial;
    return (state) => {
      const gc = window.goatcounter;
      for (const key of ["state", "cat", "sector", "stage", "focus"]) {
        if (state[key] && state[key] !== prev[key] && gc?.count) {
          gc.count({ path: `filter/${key}/${state[key]}`, title: `Filter: ${key} = ${state[key]}`, event: true });
        }
      }
      prev = state;
    };
  }

  /** Buttons with aria-expanded show and hide the element named by aria-controls. */
  function initDisclosures() {
    for (const btn of document.querySelectorAll("button.disclosure[aria-controls]")) {
      btn.addEventListener("click", () => {
        const open = btn.getAttribute("aria-expanded") !== "true";
        btn.setAttribute("aria-expanded", String(open));
        $(btn.getAttribute("aria-controls")).hidden = !open;
      });
    }
  }

  function showError(err) {
    const main = $("main");
    main.innerHTML = `<div class="load-error" role="alert"><h2>The data could not be shown</h2><p>${
      String(err.message).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c])}</p></div>`;
    $("filters").hidden = true;
    console.error(err);
  }

  main();

})(window.Tracker = window.Tracker || {});
