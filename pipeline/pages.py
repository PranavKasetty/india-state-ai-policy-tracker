"""Static pages that search engines and feed readers can use (written by export).

  dashboard/state/index.html          every state, with its record count and AI policy status
  dashboard/state/<slug>/index.html   one state: where it stands, its AI brief, all its records
  dashboard/state/<slug>/feed.xml     that state's newest records (RSS 2.0)
  dashboard/feed.xml                  the newest records across states
  dashboard/updates/index.html        how to follow the feeds by email or in a feed reader
  dashboard/sitemap.xml               the dashboard, the state index and every state page

The dashboard itself is one page whose filters live in the URL hash, which search
engines ignore; these pages give each state an address of its own ("Telangana AI
policy"). They are plain HTML with the dashboard's stylesheet and no scripts beyond
the theme and the visit counter (and, on the updates page, a state picker and a copy
button).

The site links people to the updates page rather than to the feeds, which a browser
shows as raw XML. (An XSLT stylesheet would style them, but Chrome is removing XSLT
and shows visitors a warning banner on pages that use it.)
"""

CONTACT = "pranav.kasetty@gmail.com"  # for corrections; keep in step with CONTACT in dashboard/js/format.js

# Third-party services that turn a feed into email or add it to a reader. Free, and
# none needs an account on our side; we never see subscribers' addresses.
EMAIL_SERVICE = ("Blogtrottr", "https://blogtrottr.com/")
READERS = (("Feedly", "https://feedly.com/i/subscription/feed/{}"),
           ("Inoreader", "https://www.inoreader.com/?add_feed={}"))
import html
import re
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote

from .classify import CATEGORY_IDS
from .profiles import FIELDS as PROFILE_FIELDS
from .regional import LANGUAGE_NAMES as LANGUAGES
from .stage import LABELS as STAGE_LABELS
from .states import state_code

SITE = "https://pranavkasetty.github.io/india-state-ai-policy-tracker/"
DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard"
FEED_SIZE, STATE_FEED_SIZE = 50, 30

CELL_NAMES = {"ai_policy": "AI policy", "ai_body": "Dedicated AI body", "funding": "State AI funding",
              "infrastructure": "AI infrastructure"}
CELL_WORDS = {"ai_policy": ("Adopted", "Announced"), "ai_body": ("Set up", "Announced"),
              "funding": ("Allocated", "Announced"), "infrastructure": ("Set up", "Announced")}
CITES_RE = re.compile(r"\s*\[\s*(R[0-9a-f]{8}(?:\s*,\s*R[0-9a-f]{8})*)\s*\]")

e = html.escape


def slug(state: str) -> str:
    """Same rule as stateSlug in dashboard/js/format.js."""
    return re.sub(r"[^a-z0-9]+", "-", state.lower()).strip("-")


def _long_date(iso: str) -> str:
    if len(iso) >= 10:
        d = date.fromisoformat(iso[:10])
        return f"{d.day} {d:%B %Y}"
    if len(iso) == 7:
        return datetime.strptime(iso, "%Y-%m").strftime("%B %Y")
    return iso or "Date unknown"


def _head(title: str, description: str, path: str, depth: int, feed: str | None = None) -> str:
    up = "../" * depth
    alt = f'\n  <link rel="alternate" type="application/rss+xml" title="{e(title)}" href="{e(feed)}">' if feed else ""
    return f"""<!doctype html>
<html lang="en-IN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{e(title)}</title>
  <link rel="canonical" href="{SITE}{path}">
  <meta name="description" content="{e(description)}">
  <link rel="icon" href="{up}favicon.svg" type="image/svg+xml">{alt}
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Indian States AI Policy Tracker">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(description)}">
  <meta property="og:url" content="{SITE}{path}">
  <meta property="og:image" content="{SITE}social.png">
  <meta name="twitter:card" content="summary_large_image">
  <script>
    try {{ var t = localStorage.getItem("tracker-theme"); if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; }} catch (e) {{}}
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Mukta:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{up}css/tokens.css">
  <link rel="stylesheet" href="{up}css/style.css">
  <script data-goatcounter="https://india-state-ai-tracker.goatcounter.com/count" async
    src="https://gc.zgo.at/count.v4.js" crossorigin="anonymous"
    integrity="sha384-nRw6qfbWyJha9LhsOtSb2YJDyZdKvvCFh0fJYlkquSFjUxp9FVNugbfy8q1jdxI+"></script>
</head>
<body>
  <div class="page">
"""


def _foot(depth: int, updated: str) -> str:
    up = "../" * depth
    return f"""    <footer class="static-foot">
      <p>From the <a href="{up}">Indian States AI Policy Tracker</a>: AI-related actions by India's state
      governments, gathered daily from English, Hindi and Marathi news. Data last updated {e(updated)}.
      <a href="https://github.com/PranavKasetty/india-state-ai-policy-tracker/blob/main/data/README.md">How the data is made</a>.
      Data licence: <a href="https://github.com/PranavKasetty/india-state-ai-policy-tracker/blob/main/data/LICENSE.md">CC BY 4.0</a>;
      headlines and summaries belong to their publishers. Spotted a mistake?
      <a href="mailto:{CONTACT}?subject=Indian%20States%20AI%20Policy%20Tracker">Email a correction</a>.</p>
    </footer>
  </div>
</body>
</html>
"""


def _status_rows(profile: dict, cite_href) -> str:
    rows = []
    for f in PROFILE_FIELDS:
        cell = profile.get(f) or {}
        if cell.get("status") in ("done", "announced"):
            word = CELL_WORDS[f][0 if cell["status"] == "done" else 1]
            cites = ", ".join(f'<a class="cite" href="{cite_href(c)}">{i + 1}</a>' for i, c in enumerate(cell["cites"]))
            link = cell.get("document") or cell.get("source")
            value = (f'<span class="st st-{cell["status"]}">{word}</span> {e(cell["text"])}'
                     + (f' <span class="cites">[{cites}]</span>' if cites else "")
                     + (f' <a class="st-doc" href="{e(link)}" rel="noopener">'
                        f'{"Government document" if cell.get("document") else "Report"}</a>' if link else ""))
        else:
            value = '<span class="st-none">None found</span>'
        rows.append(f"<div><dt>{CELL_NAMES[f]}</dt><dd>{value}</dd></div>")
    return "\n".join(rows)


def _brief_html(text: str, known: set[str]) -> str:
    def cites(m: re.Match) -> str:
        ids = [i for i in re.split(r"\s*,\s*", m[1]) if i in known]
        return (" <span class=\"cites\">[" + ", ".join(f'<a class="cite" href="#{i}">{n + 1}</a>'
                                                       for n, i in enumerate(ids)) + "]</span>") if ids else ""
    out, last = [], 0
    for m in CITES_RE.finditer(text):
        out.append(e(text[last:m.start()]) + cites(m))
        last = m.end()
    out.append(e(text[last:]))
    return re.sub(r"\s*\[[^\]<]*\]", "", "".join(out))  # brackets left with no valid ID


def _record(r: dict) -> str:
    others = r.get("also_reported_by") or []
    by = e(r["source_name"]) + (f" and {len(others)} other outlet{'s' if len(others) > 1 else ''}" if others else "")
    stage = r.get("stage")
    stage_tag = f'<li class="stage" data-stage="{stage}">{STAGE_LABELS[stage]}</li>' if stage in STAGE_LABELS else ""
    tags = "".join(f'<li class="tag{" primary" if t == r["primary_category"] else ""}" data-cat="{CATEGORY_IDS[t]}">{e(t)}</li>'
                   for t in r["tags"])
    lang = LANGUAGES.get(r.get("language") or "en")
    if lang and r.get("title_original"):
        summary = f'<p class="item-original" lang="{r["language"]}">{e(r["title_original"])}</p>'
        stage_tag = f'<li class="translated">Translated from {lang}</li>' + stage_tag
    else:
        summary = (f'<p class="item-summary">{e(r["summary"])}</p>'
                   if r.get("summary_source") == "publisher standfirst" and r.get("summary") else "")
    # As on the dashboard: the publisher's image over a tile with the state code, which
    # is what remains when there is no image or it fails to load (hotlinking blocked).
    img = (f'<img src="{e(r["image_url"])}" alt="" loading="lazy" decoding="async" '
           f'referrerpolicy="no-referrer" onerror="this.remove()">' if r.get("image_url") else "")
    return f"""<li class="item static-item" id="{r['record_id']}">
        <div class="thumb" aria-hidden="true"><span class="thumb-code">{e(state_code(r["state"]) or "")}</span>{img}</div>
        <div class="item-body">
          <h3 class="item-title"><a href="{e(r['source_url'])}" rel="noopener">{e(r['title'])}</a></h3>
          {summary}
          <p class="item-meta">{_long_date(r['date'] or '')}. Reported by {by}.</p>
          <ul class="item-tags">{stage_tag}{tags}<li class="sector">{e(r['sector'])}</li></ul>
        </div>
      </li>"""


def state_page(state: str, recs: list[dict], profile: dict, brief: dict | None, updated: str, start: str) -> str:
    n = len(recs)
    action = sum(r.get("stage") in ("decided", "underway") for r in recs)
    policy = (profile.get("ai_policy") or {})
    policy_phrase = {"done": f"AI policy: {policy.get('text')}", "announced": f"AI policy announced: {policy.get('text')}"}.get(
        policy.get("status"), "no state AI policy found in the news")
    title = f"{state} AI policy and initiatives: what the government is doing on AI"
    desc = (f"{n} AI developments by the {state} government since {start}, tracked from the news: "
            f"{policy_phrase}. Updated daily.")
    known = {r["record_id"] for r in recs}
    brief_block = ""
    if brief and brief.get("text"):
        brief_block = f"""
    <section class="panel" aria-labelledby="brief-title">
      <h2 id="brief-title">Summary</h2>
      <p class="brief-label">AI-generated from the developments below, each point citing them; check before quoting.</p>
      <p class="static-brief">{_brief_html(brief['text'], known)}</p>
    </section>"""
    by_type: dict[str, int] = {}
    for r in recs:
        for t in r["tags"]:
            by_type[t] = by_type.get(t, 0) + 1
    types = ", ".join(f"{t.lower()} {c}" for t, c in sorted(by_type.items(), key=lambda x: -x[1]))
    items = "\n      ".join(_record(r) for r in recs)
    return _head(title, desc, f"state/{slug(state)}/", 2, "feed.xml") + f"""    <nav class="crumbs" aria-label="Breadcrumb"><a href="../../">Indian States AI Policy Tracker</a> / <a href="../">States</a> / {e(state)}</nav>
    <header class="masthead static-head">
      <div>
        <h1>{e(state)}: AI policy and activity</h1>
        <p class="lede">What the {e(state)} government has done on AI, as reported in the news since {e(start)}:
        {n} developments, {action} of them approved, signed, launched or in use.</p>
      </div>
    </header>
    <main>
    <section class="panel" aria-labelledby="stand-title">
      <h2 id="stand-title">Where {e(state)} stands</h2>
      <p class="panel-sub">Drafted by a language model from the news records and linked to them; some are corrected
      by hand and link the government's document or a report instead. "None found"
      means the news we collect does not show it, not that the state has none.</p>
      <dl class="static-status">
{_status_rows(profile, lambda c: f"#{c}")}
      </dl>
    </section>{brief_block}
    <section class="panel" aria-labelledby="list-title">
      <h2 id="list-title">All {n} developments</h2>
      <p class="panel-sub">Newest first. By type: {e(types)}.
      <a href="../../#state={quote(state)}">Filter and chart them in the tracker</a>,
      or <a href="../../updates/#{slug(state)}">get new ones by email or in a feed reader</a>.</p>
      <ol class="item-list static-list">
      {items}
      </ol>
    </section>
    </main>
""" + _foot(2, updated)


def index_page(states: list[str], by_state: dict, profiles: dict, updated: str) -> str:
    rows = []
    for s in states:
        p = (profiles.get(s) or {}).get("ai_policy") or {}
        status = {"done": "AI policy adopted", "announced": "AI policy announced"}.get(p.get("status"), "No AI policy found")
        rows.append(f'<li><a href="{slug(s)}/">{e(s)}</a> <span class="static-count">{len(by_state.get(s, []))} developments. {status}.</span></li>')
    return _head("AI policy in India's states: one page per state", "What each of India's 28 state "
                 "governments is doing on AI: policies, bodies, funding, infrastructure and every development "
                 "reported in the news.", "state/", 1, "../feed.xml") + f"""    <nav class="crumbs" aria-label="Breadcrumb"><a href="../">Indian States AI Policy Tracker</a> / States</nav>
    <header class="masthead static-head"><div><h1>AI policy in India's states</h1>
      <p class="lede">One page per state: where it stands on AI policy, a summary, and every development reported in the news.</p></div></header>
    <main>
    <section class="panel"><ul class="static-states">
      {chr(10).join(rows)}
    </ul></section>
    </main>
""" + _foot(1, updated)


def updates_page(states: list[str], updated: str) -> str:
    """How to follow new developments, for all states or one, by email or in a feed reader.
    The picker sets the feed in every option; #<slug> in the address preselects a state."""
    options = "".join(f'<option value="state/{slug(s)}/feed.xml" data-slug="{slug(s)}">{e(s)}</option>' for s in states)
    readers = " ".join(f'<a class="sub-btn" data-reader="{e(url)}" href="{e(url.format(quote(SITE + "feed.xml", safe="")))}" '
                       f'target="_blank" rel="noopener">Add to {name}<span class="visually-hidden"> (opens in a new tab)</span></a>'
                       for name, url in READERS)
    name, service = EMAIL_SERVICE
    return _head("Get new AI developments by email or feed", "Follow new AI developments by India's state "
                 "governments, for every state or just one, by email or in a feed reader. Updated daily.",
                 "updates/", 1, "../feed.xml") + f"""    <nav class="crumbs" aria-label="Breadcrumb"><a href="../">Indian States AI Policy Tracker</a> / Get updates</nav>
    <header class="masthead static-head"><div><h1>Get new developments as they are reported</h1>
      <p class="lede">The tracker adds new developments every morning. Follow every state or just one, by email or in a feed reader.</p></div></header>
    <main>
    <section class="panel updates">
      <label class="updates-pick">Follow
        <select id="feed-pick"><option value="feed.xml" data-slug="">All states</option>{options}</select>
      </label>

      <h2>By email</h2>
      <p class="panel-sub">{name} is a free service that emails you a feed's new entries. We never see your address.</p>
      <ol class="updates-steps">
        <li>Copy the feed address:
          <span class="feed-copy"><input id="feed-url" type="text" readonly value="{SITE}feed.xml" aria-label="Feed address">
          <button type="button" class="sub-btn" id="feed-copy-btn">Copy</button></span></li>
        <li>Open <a href="{service}" target="_blank" rel="noopener">{name}<span class="visually-hidden"> (opens in a new tab)</span></a>,
          paste the address into "Feed URL" and enter your email address.</li>
        <li>Choose how often: as entries arrive, or a daily digest. Then confirm the email {name} sends you.</li>
      </ol>

      <h2>In a feed reader</h2>
      <p class="panel-sub">One click adds the feed to these readers. Any other reader, and the RSS apps for Slack
      and Microsoft Teams, take the feed address above.</p>
      <p class="updates-readers">{readers}</p>

      <h2>What you get</h2>
      <p class="panel-sub">Each new development: its headline, state, types and stage, a link to the
      report, and a link to it in the tracker. The all-states feed carries the newest {FEED_SIZE}, each state's feed its
      newest {STATE_FEED_SIZE}.</p>
    </section>
    </main>
    <script>
      (function () {{
        var site = "{SITE}", pick = document.getElementById("feed-pick"), box = document.getElementById("feed-url");
        function show() {{
          var url = site + pick.value;
          box.value = url;
          document.querySelectorAll("[data-reader]").forEach(function (a) {{
            a.href = a.dataset.reader.replace("{{}}", encodeURIComponent(url));
          }});
        }}
        var want = location.hash.slice(1);
        if (want) for (var i = 0; i < pick.options.length; i++) if (pick.options[i].dataset.slug === want) pick.selectedIndex = i;
        pick.addEventListener("change", function () {{
          var o = pick.options[pick.selectedIndex];
          history.replaceState(null, "", o.dataset.slug ? "#" + o.dataset.slug : location.pathname);
          show();
        }});
        document.getElementById("feed-copy-btn").addEventListener("click", function () {{
          var b = this;
          (navigator.clipboard ? navigator.clipboard.writeText(box.value) : Promise.reject()).then(function () {{
            b.textContent = "Copied";
            setTimeout(function () {{ b.textContent = "Copy"; }}, 2000);
          }}, function () {{ box.select(); }});
        }});
        show();
      }})();
    </script>
""" + _foot(1, updated)


def _rss(title: str, link: str, description: str, recs: list[dict], self_url: str) -> str:
    items = []
    for r in recs:
        try:
            when = datetime.fromisoformat((r["date"] or "")[:10]).replace(hour=12, tzinfo=timezone.utc)
        except ValueError:
            when = None
        entry = f"{SITE}#item={r['record_id']}"
        stage = STAGE_LABELS.get(r.get("stage") or "", "")
        body = (f"<p>{e(r['summary'] if r.get('summary_source') == 'publisher standfirst' else '')}</p>"
                f"<p>{e(r['state'])}. {e(', '.join(r['tags']))}{'. ' + stage if stage else ''}. "
                f"Reported by {e(r['source_name'])}. <a href=\"{e(entry)}\">See it in the tracker</a>.</p>")
        items.append(f"""  <item>
    <title>{e(r['state'])}: {e(r['title'])}</title>
    <link>{e(r['source_url'])}</link>
    <guid isPermaLink="true">{e(entry)}</guid>
    {f'<pubDate>{format_datetime(when)}</pubDate>' if when else ''}
    <category>{e(r['state'])}</category>
    <description>{e(body)}</description>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{e(title)}</title>
  <link>{e(link)}</link>
  <description>{e(description)}</description>
  <language>en-IN</language>
  <atom:link href="{e(self_url)}" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
</channel>
</rss>
"""


def write_all(records: list[dict], briefs: dict, profiles: dict) -> None:
    updated = _long_date(datetime.now(timezone.utc).date().isoformat())
    dates = sorted(r["date"] for r in records if r["date"])
    start = _long_date(dates[0][:7]) if dates else ""
    newest = sorted(records, key=lambda r: r["date"] or "", reverse=True)
    states = sorted({r["state"] for r in records})
    by_state = {s: [r for r in newest if r["state"] == s] for s in states}

    for s in states:
        folder = DASHBOARD / "state" / slug(s)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(
            state_page(s, by_state[s], profiles.get(s) or {}, briefs.get(f"state:{s}"), updated, start), encoding="utf-8")
        (folder / "feed.xml").write_text(_rss(
            f"{s}: AI policy tracker", f"{SITE}state/{slug(s)}/",
            f"New AI developments by the {s} government, from the Indian States AI Policy Tracker.",
            by_state[s][:STATE_FEED_SIZE], f"{SITE}state/{slug(s)}/feed.xml"), encoding="utf-8")
    (DASHBOARD / "state" / "index.html").write_text(index_page(states, by_state, profiles, updated), encoding="utf-8")
    (DASHBOARD / "updates").mkdir(exist_ok=True)
    (DASHBOARD / "updates" / "index.html").write_text(updates_page(states, updated), encoding="utf-8")
    (DASHBOARD / "feed.xml").write_text(_rss(
        "Indian States AI Policy Tracker", SITE,
        "New AI developments by India's state governments, gathered daily from the news.",
        newest[:FEED_SIZE], f"{SITE}feed.xml"), encoding="utf-8")

    today = datetime.now(timezone.utc).date().isoformat()
    urls = ["", "state/", "updates/", *[f"state/{slug(s)}/" for s in states]]
    (DASHBOARD / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- Written by pipeline/pages.py. Submitted in Google Search Console. -->\n"
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq></url>\n" for u in urls)
        + "</urlset>\n", encoding="utf-8")
    print(f"pages: {len(states)} state pages, feeds and sitemap -> {DASHBOARD}")
