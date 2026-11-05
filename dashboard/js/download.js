// "Download these as CSV": the developments passing the current filters, newest
// first, in the browser (no request). Columns follow data/output/records.csv where
// the dashboard has the field. Starts with a byte-order mark so Excel reads the
// Hindi and Marathi headlines as UTF-8.
(function (T) {
  "use strict";
  const { permalink, stateSlug } = T.format;
  const SITE = "https://pranavkasetty.github.io/india-state-ai-policy-tracker/"; // links in a saved file point to the live site

  const COLUMNS = [
    ["record_id", (it) => it.id],
    ["date", (it) => it.date],
    ["state", (it) => it.state],
    ["title", (it) => it.title],
    ["title_original", (it) => it.title_original || ""],
    ["language", (it) => it.lang || "en"],
    ["stage", (it, d) => d.stage[it.stage] || ""],
    ["primary_category", (it, d) => d.label[it.category] || it.category],
    ["tags", (it, d) => it.tags.map((t) => d.label[t] || t).join("; ")],
    ["sector", (it) => it.sector],
    ["n_sources", (it) => 1 + it.alsoReportedBy.length],
    ["source_name", (it) => it.source],
    ["also_reported_by", (it) => it.alsoReportedBy.join("; ")],
    ["source_url", (it) => it.url],
    ["summary", (it) => (it.summary && it.summary !== it.title ? it.summary : "")],
    ["tracker_url", (it) => permalink(it.id, SITE)],
  ];

  const cell = (v) => {
    const s = String(v ?? "");
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };

  function toCsv(items, data) {
    const d = { label: data.categoryLabel, stage: Object.fromEntries((data.meta.stages || []).map((s) => [s.id, s.label])) };
    const rows = [...items].sort((a, b) => (b.date || "").localeCompare(a.date || ""))
      .map((it) => COLUMNS.map(([, get]) => cell(get(it, d))).join(","));
    return "﻿" + [COLUMNS.map(([name]) => name).join(","), ...rows].join("\r\n") + "\r\n";
  }

  /** A file name that says what was filtered: india-ai-tracker-bihar-2026-11-05.csv */
  function fileName(state, end) {
    return `india-ai-tracker${state.state ? "-" + stateSlug(state.state) : ""}${state.cat ? "-" + state.cat : ""}-${end}.csv`;
  }

  function save(items, data, state) {
    const url = URL.createObjectURL(new Blob([toCsv(items, data)], { type: "text/csv;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: fileName(state, data.meta.period_end) });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  T.download = { toCsv, fileName, save };
})(window.Tracker = window.Tracker || {});
