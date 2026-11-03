// Filtering and aggregation: pure functions over the prepared dataset (dataset.js),
// shared by every view so all panels count the same way.
(function (T) {
  "use strict";
  /** The filter keys and their "unset" values. Order is the URL order. */
  function defaultFilters(data) {
    return { state: "", cat: "", sector: "", focus: "", from: data.months[0] || "", to: data.months.at(-1) || "", q: "" };
  }

  // "Policy actions only" (focus=policy): types that commit a government to something
  // (a policy, a rule, a body, money or a signed agreement), leaving out deployments,
  // infrastructure, skilling and events. Types come from headlines, so an announced
  // plan counts as well as an adopted one.
  const POLICY_TYPES = ["strategy_policy", "regulation_ethics", "governance_body", "funding_budget", "partnership"];
  const FOCUS = { policy: (it) => it.tags.some((t) => POLICY_TYPES.includes(t)) };

  const isFullRange = (data, filters) =>
    filters.from === data.months[0] && filters.to === data.months.at(-1);

  /**
   * Items passing every filter except those named in `ignore`.
   * - A category matches any item carrying that tag, primary or not.
   * - Items whose month is unknown pass the date filter only when it spans the whole period.
   */
  function filterItems(data, filters, { ignore = [] } = {}) {
    const use = (key) => filters[key] && !ignore.includes(key);
    const q = filters.q.trim().toLowerCase();
    const full = isFullRange(data, filters);
    return data.items.filter((it) =>
      (!use("state") || it.state === filters.state) &&
      (!use("cat") || it.tags.includes(filters.cat)) &&
      (!use("sector") || it.sector === filters.sector) &&
      (!use("focus") || (FOCUS[filters.focus] || (() => true))(it)) &&
      (it.month ? it.month >= filters.from && it.month <= filters.to : full) &&
      (!q || it.search.includes(q)));
  }

  /** Months of the period inside the filter's range. */
  const monthsInRange = (data, filters) =>
    data.months.filter((m) => m >= filters.from && m <= filters.to);

  /** { month: count } for the given months, zero-filled. Items without a month are skipped. */
  function countByMonth(items, months) {
    const counts = Object.fromEntries(months.map((m) => [m, 0]));
    for (const it of items) if (it.month in counts) counts[it.month]++;
    return counts;
  }

  /**
   * One row per state: total items, items per category tag, items per month.
   * Category counts can sum to more than the total because items carry several tags.
   * Rows are sorted by total, largest first.
   */
  function stateByCategory(items, data, months) {
    const rows = new Map(data.meta.states.map((s) => [s.name, {
      state: s.name,
      total: 0,
      byCategory: Object.fromEntries(data.meta.categories.map((c) => [c.id, 0])),
      byMonth: Object.fromEntries(months.map((m) => [m, 0])),
    }]));
    for (const it of items) {
      const row = rows.get(it.state);
      if (!row) continue;
      row.total++;
      for (const t of it.tags) if (t in row.byCategory) row.byCategory[t]++;
      if (it.month in row.byMonth) row.byMonth[it.month]++;
    }
    return [...rows.values()].sort((a, b) => b.total - a.total || a.state.localeCompare(b.state));
  }

  /**
   * Count items per state ("state") or per category tag ("cat"), as
   * [{ id, label, n }] sorted largest first. Every state/category appears, even at 0.
   */
  function rankBy(items, data, dimension) {
    const options = dimension === "state"
      ? data.meta.states.map((s) => ({ id: s.name, label: s.name }))
      : data.meta.categories.map((c) => ({ id: c.id, label: c.label }));
    const counts = Object.fromEntries(options.map((o) => [o.id, 0]));
    for (const it of items) {
      for (const key of dimension === "state" ? [it.state] : it.tags) if (key in counts) counts[key]++;
    }
    return options.map((o) => ({ ...o, n: counts[o.id] }))
      .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label));
  }

  // ---------- sorting the list ----------

  const DAY_MS = 86400000;
  const UNDATED_DAYS = 365; // records without a day-precise date count as old for "trending"

  /** Distinct outlets that reported it: n_sources from the pipeline, else 1 + also-reported. */
  const outlets = (it) => (Number.isInteger(it.n_sources) ? it.n_sources : 1 + it.alsoReportedBy.length);

  function daysOld(it, today) {
    if (it.precision !== "day") return UNDATED_DAYS;
    const t = Date.parse(`${it.date}T00:00:00Z`);
    return Number.isNaN(t) ? UNDATED_DAYS : Math.max(0, Math.floor((today - t) / DAY_MS));
  }

  /** Coverage decayed by age: more outlets and fewer days old score higher. */
  const trendScore = (it, today) => outlets(it) / (daysOld(it, today) + 2) ** 1.2;

  // Dates are ISO strings (or partial/empty), so string order is date order.
  const byDateDesc = (a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0);

  const SORTS = {
    newest: () => byDateDesc,
    covered: () => (a, b) => outlets(b) - outlets(a) || byDateDesc(a, b),
    trending: (today) => {
      const score = new Map();
      const s = (it) => { if (!score.has(it)) score.set(it, trendScore(it, today)); return score.get(it); };
      return (a, b) => s(b) - s(a) || byDateDesc(a, b);
    },
  };

  /** A sorted copy. `today` (ms since epoch, UTC midnight) is a parameter so tests are stable. */
  function sortItems(items, mode, today = utcToday()) {
    return [...items].sort((SORTS[mode] || SORTS.newest)(today));
  }

  function utcToday() {
    const d = new Date();
    return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
  }

  T.query = { defaultFilters, isFullRange, POLICY_TYPES, FOCUS_VALUES: Object.keys(FOCUS), filterItems, monthsInRange, countByMonth, stateByCategory, rankBy,
    sortItems, trendScore, outlets, SORT_MODES: Object.keys(SORTS) };
})(window.Tracker = window.Tracker || {});
