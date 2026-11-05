// Unit tests for the dashboard's pure logic (dashboard/js/format.js, query.js, dataset.js).
// The scripts are browser scripts that attach to window.Tracker, so they are loaded
// into a sandbox with a stand-in window.
//
// Run:  node --test tests/
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function load() {
  const sandbox = { Intl, console, URLSearchParams };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  for (const f of ["format.js", "query.js", "dataset.js", "download.js"]) {
    const file = path.join(__dirname, "..", "dashboard", "js", f);
    vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
  }
  return sandbox.Tracker;
}
const T = load();
// Values made inside the sandbox have its own prototypes; copy them out before deepEqual.
const plain = (x) => JSON.parse(JSON.stringify(x));

const RAW = {
  meta: {
    is_mock: true, generated_at: "2026-11-01T00:00:00+00:00",
    period_start: "2026-01-01", period_end: "2026-03-31",
    states: [{ name: "Kerala", code: "KL" }, { name: "Bihar", code: "BR" }],
    categories: [{ id: "deployment", label: "Deployment" }, { id: "skilling", label: "Skilling" }],
    sectors: ["Health", "Education"],
  },
  items: [
    { id: "1", date: "2026-01-10", state: "Kerala", title: "Kerala AI chatbot", source: "A", url: "", category: "deployment", tags: ["deployment"], sector: "Health" },
    { id: "2", date: "2026-02-05", state: "Kerala", title: "Kerala trains staff", source: "B", url: "", category: "skilling", tags: ["skilling", "deployment"], sector: "Education" },
    { id: "3", date: "2026-03", date_precision: "month", state: "Bihar", title: "Bihar AI mission", source: "C", url: "", category: "deployment", tags: ["deployment"], sector: "Health" },
    { id: "4", date: "2026", date_precision: "year", state: "Bihar", title: "Bihar AI plan", source: "D", url: "", category: "skilling", tags: ["skilling"], sector: "Health", also_reported_by: "X; Y" },
  ],
};
const data = T.dataset.loadDataset(RAW);
const all = T.query.defaultFilters(data);

test("monthRange spans year boundaries", () => {
  assert.deepEqual(plain(T.format.monthRange("2025-11", "2026-02")), ["2025-11", "2025-12", "2026-01", "2026-02"]);
});

test("niceStep rounds up to 1, 2, 2.5, 5 or 10 times a power of ten", () => {
  assert.equal(T.format.niceStep(0.7), 1);
  assert.equal(T.format.niceStep(4.2), 5);
  assert.equal(T.format.niceStep(23), 25);
  assert.equal(T.format.niceStep(0), 1);
});

test("esc escapes HTML", () => {
  assert.equal(T.format.esc(`<a href="x">&'</a>`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
});

test("dataset derives months and handles partial dates", () => {
  assert.deepEqual(plain(data.months), ["2026-01", "2026-02", "2026-03"]);
  const byId = Object.fromEntries(data.items.map((it) => [it.id, it]));
  assert.equal(byId["3"].month, "2026-03");
  assert.equal(byId["4"].month, null);
  assert.deepEqual(plain(byId["4"].alsoReportedBy), ["X", "Y"]);
});

test("dataset rejects data with an unknown state", () => {
  const bad = structuredClone(RAW);
  bad.items[0].state = "Goa";
  assert.throws(() => T.dataset.loadDataset(bad), /unknown state/);
});

test("category filter matches secondary tags", () => {
  const ids = T.query.filterItems(data, { ...all, cat: "deployment" }).map((it) => it.id);
  assert.deepEqual(plain(ids), ["1", "2", "3"]);
});

test("records without a month only appear for the full date range", () => {
  assert.equal(T.query.filterItems(data, all).length, 4);
  const narrowed = T.query.filterItems(data, { ...all, from: "2026-02" }).map((it) => it.id);
  assert.deepEqual(plain(narrowed), ["2", "3"]);
});

test("filterItems can ignore chosen filters", () => {
  const f = { ...all, state: "Kerala", sector: "Health" };
  assert.equal(T.query.filterItems(data, f).length, 1);
  assert.equal(T.query.filterItems(data, f, { ignore: ["state"] }).length, 3);
});

test("search covers headline text, case-insensitively", () => {
  assert.equal(T.query.filterItems(data, { ...all, q: "CHATBOT" }).length, 1);
});

test("stateByCategory counts tags and sorts by total", () => {
  const rows = T.query.stateByCategory(data.items, data, data.months);
  assert.deepEqual(plain(rows.map((r) => r.state)), ["Bihar", "Kerala"]); // tie on 2, then alphabetical
  const kerala = rows.find((r) => r.state === "Kerala");
  assert.equal(kerala.total, 2);
  assert.equal(kerala.byCategory.deployment, 2); // record 2 carries it as a secondary tag
  assert.equal(kerala.byMonth["2026-02"], 1);
});

test("countByMonth zero-fills and skips undated records", () => {
  const counts = T.query.countByMonth(data.items, data.months);
  assert.deepEqual(plain(counts), { "2026-01": 1, "2026-02": 1, "2026-03": 1 });
});

test("rankBy counts per state and per tag, largest first, keeping zeros", () => {
  const states = T.query.rankBy(data.items, data, "state");
  assert.deepEqual(plain(states.map((r) => [r.id, r.n])), [["Bihar", 2], ["Kerala", 2]]);
  const types = T.query.rankBy(data.items, data, "cat");
  assert.deepEqual(plain(types.map((r) => [r.id, r.label, r.n])), [["deployment", "Deployment", 3], ["skilling", "Skilling", 2]]);
  const none = T.query.rankBy([], data, "cat");
  assert.deepEqual(plain(none.map((r) => r.n)), [0, 0]);
});

test("sortItems: newest, most covered and trending", () => {
  const today = Date.UTC(2026, 2, 1); // 1 Mar 2026
  const mk = (id, date, n, precision = "day") => ({ id, date, precision, n_sources: n, alsoReportedBy: [] });
  const items = [
    mk("old-big", "2026-01-01", 6),   // 59 days old, 6 outlets
    mk("new-one", "2026-02-28", 1),   // 1 day old, 1 outlet
    mk("new-two", "2026-02-27", 2),   // 2 days old, 2 outlets
    mk("partial", "2026-02", 9, "month"), // month-only date: treated as 365 days old
  ];
  const ids = (mode) => plain(T.query.sortItems(items, mode, today).map((it) => it.id));
  assert.deepEqual(ids("newest"), ["new-one", "new-two", "partial", "old-big"]);
  assert.deepEqual(ids("covered"), ["partial", "old-big", "new-two", "new-one"]);
  // scores: new-two 2/4^1.2=0.38, new-one 1/3^1.2=0.27, old-big 6/61^1.2=0.04, partial 9/367^1.2=0.008
  assert.deepEqual(ids("trending"), ["new-two", "new-one", "old-big", "partial"]);
  assert.deepEqual(ids("unknown-mode"), ids("newest"));
  assert.deepEqual(plain(items.map((it) => it.id)), ["old-big", "new-one", "new-two", "partial"], "input not mutated");
});

test("outlets falls back to also-reported-by when n_sources is missing", () => {
  const it4 = data.items.find((it) => it.id === "4");
  assert.equal(T.query.outlets(it4), 3);
  assert.equal(T.query.outlets(data.items.find((it) => it.id === "1")), 1);
});

test("policy focus keeps only records with a policy-type tag", () => {
  const raw = structuredClone(RAW);
  raw.meta.categories.push({ id: "funding_budget", label: "Funding & budget" });
  raw.items[1].tags.push("funding_budget");
  const d = T.dataset.loadDataset(raw);
  const f = T.query.defaultFilters(d);
  assert.equal(f.focus, "");
  assert.deepEqual(plain(T.query.filterItems(d, { ...f, focus: "policy" }).map((it) => it.id)), ["2"]);
  assert.equal(T.query.filterItems(d, { ...f, focus: "policy" }, { ignore: ["focus"] }).length, 4);
});

test("dataset flags the last month when the data stops before its end", () => {
  assert.equal(data.partialMonth, null, "period ends on 31 Mar");
  const raw = structuredClone(RAW);
  raw.meta.period_end = "2026-03-09";
  assert.deepEqual(plain(T.dataset.loadDataset(raw).partialMonth), { month: "2026-03", through: "2026-03-09" });
});

test("repairText fixes UTF-8 read as Latin-1 and leaves other text alone", () => {
  assert.equal(T.dataset.repairText("Lucknowâ\u0080\u0099s policing"), "Lucknow’s policing");
  assert.equal(T.dataset.repairText("Café ₹1,725 crore"), "Café ₹1,725 crore");
  assert.equal(T.dataset.repairText("The stateâ\u0080\u0099s system…"), "The state’s system…", "mixed with real Unicode");
  assert.equal(T.dataset.repairText(undefined), undefined);
});

test("stage filter: action means approved, signed, launched or in use", () => {
  const raw = structuredClone(RAW);
  raw.meta.stages = [{ id: "announced", label: "A" }, { id: "decided", label: "D" }, { id: "underway", label: "U" }];
  ["announced", "decided", "underway", ""].forEach((st, i) => { raw.items[i].stage = st; });
  const d = T.dataset.loadDataset(raw);
  const f = T.query.defaultFilters(d);
  const ids = (stage) => plain(T.query.filterItems(d, { ...f, stage }).map((it) => it.id));
  assert.deepEqual(ids("action"), ["2", "3"]);
  assert.deepEqual(ids("announced"), ["1"]);
  assert.deepEqual(ids(""), ["1", "2", "3", "4"], "unjudged records show when no stage is chosen");
});

test("permalink and issueUrl build shareable links", () => {
  assert.equal(T.format.permalink("R1a2b3c4d", "https://x.test/tracker/"), "https://x.test/tracker/#item=R1a2b3c4d");
  const url = new URL(T.format.issueUrl("Problem with R1", "Line 1\nLine 2 & more"));
  assert.equal(url.pathname, "/PranavKasetty/india-state-ai-policy-tracker/issues/new");
  assert.equal(url.searchParams.get("body"), "Line 1\nLine 2 & more");
});

test("CSV download: newest first, quoted, with readable labels and a byte-order mark", () => {
  const items = [data.items.find((it) => it.id === "1"), data.items.find((it) => it.id === "2")];
  items[0] = { ...items[0], title: 'Kerala "AI" chatbot, phase 1' };
  const csv = T.download.toCsv(items, data);
  const lines = csv.split("\r\n");
  assert.equal(lines[0].charCodeAt(0), 0xfeff);
  assert.ok(lines[0].endsWith("record_id,date,state,title,title_original,language,stage,primary_category,tags,sector,n_sources,source_name,also_reported_by,source_url,summary,tracker_url"));
  assert.ok(lines[1].startsWith("2,2026-02-05,Kerala,Kerala trains staff,,en,,Skilling,Skilling; Deployment,Education,1,B,"));
  assert.ok(lines[2].includes(',"Kerala ""AI"" chatbot, phase 1",'));
  assert.equal(T.download.fileName({ state: "Tamil Nadu", cat: "" }, "2026-11-05"), "india-ai-tracker-tamil-nadu-2026-11-05.csv");
});
