// Formatting and small pure helpers. No DOM access, so these are unit-testable.
(function (T) {
  "use strict";
  const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];
  const numberFormat = new Intl.NumberFormat("en-IN");

  /** Every "YYYY-MM" from a to b inclusive. */
  function monthRange(a, b) {
    const out = [];
    let [y, m] = a.split("-").map(Number);
    const [yb, mb] = b.split("-").map(Number);
    while (y < yb || (y === yb && m <= mb)) {
      out.push(`${y}-${String(m).padStart(2, "0")}`);
      if (++m > 12) { m = 1; y++; }
    }
    return out;
  }

  const monthShort = (ym) => MONTH_NAMES[Number(ym.slice(5, 7)) - 1];
  const monthLong = (ym) => `${monthShort(ym)} ${ym.slice(0, 4)}`;
  const monthFull = (ym) => `${MONTH_FULL[Number(ym.slice(5, 7)) - 1]} ${ym.slice(0, 4)}`;
  const formatDate = (d) => `${Number(d.slice(8, 10))} ${monthShort(d)} ${d.slice(0, 4)}`;
  const formatNumber = (n) => numberFormat.format(n);
  const plural = (n, word, many = word + "s") => `${formatNumber(n)} ${n === 1 ? word : many}`;

  /** What one entry is called on the page. Change it here and the page follows,
      including index.html text marked with data-noun (filled in by main.js). */
  const NOUN = { one: "development", many: "developments" };
  const count = (n) => plural(n, NOUN.one, NOUN.many);
  const cap = (s) => s[0].toUpperCase() + s.slice(1);
  /** Fill {one} {many} {One} {Many} in a template. */
  const nounText = (t) => t.replace(/\{(one|many|One|Many)\}/g, (_, k) =>
    k === "one" ? NOUN.one : k === "many" ? NOUN.many : cap(k === "One" ? NOUN.one : NOUN.many));

  /** Escape text for insertion into HTML. Use on every data value rendered via innerHTML. */
  function esc(value) {
    return String(value).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  /** Round a raw step up to 1, 2, 2.5 or 5 times a power of ten. */
  function niceStep(raw) {
    if (!(raw > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(raw)));
    const f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }

  // ---------- links out ----------

  const REPO = "https://github.com/PranavKasetty/india-state-ai-policy-tracker";

  /** A GitHub "new issue" link with the title and body filled in. */
  const issueUrl = (title, body) => `${REPO}/issues/new?${new URLSearchParams({ title, body })}`;
  /** The no-account way to report a problem (keep in step with CONTACT in pipeline/pages.py). */
  const CONTACT = "pranav.kasetty@gmail.com";
  const mailUrl = (subject, body) => `mailto:${CONTACT}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  /** The page address that opens on record `id` (main.js reads #item=). */
  const permalink = (id, base = location.origin + location.pathname) => `${base}#item=${encodeURIComponent(id)}`;

  /** URL segment of a state's page (pipeline/pages.py writes state/<slug>/). */
  const stateSlug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  T.format = { REPO, CONTACT, issueUrl, mailUrl, permalink, stateSlug, monthRange, monthShort, monthLong, monthFull, formatDate, formatNumber, plural, esc, niceStep, NOUN, count, nounText };
})(window.Tracker = window.Tracker || {});
