// Read window.TRACKER_DATA (set by data.js, written by pipeline/export.py or
// dashboard/mock_data.py), check it against the contract in dashboard/schema.py,
// and add the derived fields the views need. Views never read the raw object.
(function (T) {
  "use strict";
  const { monthRange } = T.format;

  const MONTH_RE = /^\d{4}-\d{2}/;

  function loadDataset(raw = window.TRACKER_DATA) {
    if (!raw) {
      throw new Error("The data file (data.js) did not load. Generate it with " +
        "python -m pipeline.run, or python -m dashboard.mock_data for placeholder data.");
    }
    const problems = check(raw);
    if (problems.length) throw new Error(`data.js does not match the expected shape: ${problems.join("; ")}`);

    const { meta } = raw;
    const items = raw.items.map(prepareItem);
    const months = periodMonths(meta, items);
    return {
      meta,
      items,
      months,
      partialMonth: partialMonth(meta, months),
      categoryLabel: Object.fromEntries(meta.categories.map((c) => [c.id, c.label])),
    };
  }

  /** The last month, as { month, through } when the data stops before its end; else null. */
  function partialMonth(meta, months) {
    const end = meta.period_end;
    if (!months.length || !/^\d{4}-\d{2}-\d{2}/.test(end) || end.slice(0, 7) !== months.at(-1)) return null;
    const [y, m, d] = end.slice(0, 10).split("-").map(Number);
    const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
    return d < days ? { month: months.at(-1), through: end.slice(0, 10) } : null;
  }

  // Some publishers' pages were read as Latin-1 when they were UTF-8, so "’" arrived
  // as "â€™" (fixed in pipeline/enrich.py; this covers data built before the fix).
  // Re-decode each garbled run; a run that is not valid UTF-8 is kept as it was.
  const GARBLED = /[Â-ô][\u0080-¿]+/g;
  function repairText(s) {
    if (typeof s !== "string") return s;
    return s.replace(GARBLED, (run) => {
      try { return decodeURIComponent(escape(run)); } catch { return run; }
    });
  }

  function prepareItem(raw) {
    const it = { ...raw, title: repairText(raw.title), summary: repairText(raw.summary), source: repairText(raw.source) };
    const precision = it.date_precision || (it.date.length >= 10 ? "day" : it.date.length === 7 ? "month" : it.date ? "year" : "unknown");
    const others = Array.isArray(it.also_reported_by)
      ? it.also_reported_by
      : String(it.also_reported_by || "").split(";").map((s) => s.trim()).filter(Boolean);
    return {
      ...it,
      precision,
      // null when the month is not known; such items only appear when the date
      // filter covers the whole period (see query.filterItems).
      month: MONTH_RE.test(it.date) && precision !== "year" ? it.date.slice(0, 7) : null,
      summary: it.summary && it.summary !== it.title ? it.summary : "",
      image: it.image || "",
      alsoReportedBy: others,
      search: `${it.title} ${it.title_original || ""} ${it.summary || ""}`.toLowerCase(),
    };
  }

  /** All months of the reporting period. Falls back to the items' own range. */
  function periodMonths(meta, items) {
    let first = MONTH_RE.test(meta.period_start) ? meta.period_start.slice(0, 7) : null;
    let last = MONTH_RE.test(meta.period_end) ? meta.period_end.slice(0, 7) : null;
    const known = items.map((it) => it.month).filter(Boolean).sort();
    if (!first || (known.length && known[0] < first)) first = known[0];
    if (!last || (known.length && known.at(-1) > last)) last = known.at(-1);
    return first && last ? monthRange(first, last) : [];
  }

  // A light check: enough to fail loudly on a wrong file. The full check is schema.py.
  function check(raw) {
    const meta = raw.meta;
    if (!meta || !Array.isArray(raw.items)) return ["needs 'meta' and 'items'"];
    const out = [];
    for (const key of ["states", "categories", "sectors"]) {
      if (!Array.isArray(meta[key]) || !meta[key].length) out.push(`meta.${key} missing or empty`);
    }
    if (out.length) return out;
    const states = new Set(meta.states.map((s) => s.name));
    const cats = new Set(meta.categories.map((c) => c.id));
    const bad = raw.items.findIndex((it) =>
      typeof it.title !== "string" || typeof it.date !== "string" || !states.has(it.state) ||
      !Array.isArray(it.tags) || !it.tags.every((t) => cats.has(t)) || !cats.has(it.category));
    if (bad >= 0) out.push(`items[${bad}] has an unknown state or category, or a missing field`);
    return out;
  }

  T.dataset = { loadDataset, repairText };
})(window.Tracker = window.Tracker || {});
