"""One row per state: where it stands on four markers of AI policy (LLM, cited, cached).

For each state the LLM reads that state's records of the relevant types and fills
four cells. Each cell is a status, a short description and the record IDs it relies
on. Cited IDs are checked against the input, and a cell without a valid citation is
reset to "none", so every claim links to the news reports behind it.

  ai_policy       a state policy, mission, strategy or framework mainly about AI
                  (AI with other emerging tech counts; a general IT, GCC or
                  semiconductor policy with an AI chapter does not)
  ai_body         a dedicated AI body: mission office, task force, committee, AI
                  department or cell, or a department renamed for AI
  funding         state money for AI: a budget line, fund, grant or sanctioned amount
                  (company investment pledges in MoUs do not count)
  infrastructure  state-backed AI infrastructure: a centre of excellence, AI lab or
                  institute, compute facility or AI data centre

  status: "done" (adopted, set up, allocated, built or opened), "announced"
  (planned, proposed, promised or drafted) or "none" (not found in the news).

Stored in data/output/profiles.json with a hash of each state's input, and redone
only when that input changes.

Hand-checked corrections in data/curated/status.json replace the model's cell for a
state and marker (apply_curated): the model only sees the news since the tracking
window opened, so it misses older policies and can mistake a draft for an adopted
one. A corrected cell links the government's own document, or a report, and has no
record citations.
"""
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from . import llm

STORE = Path(__file__).resolve().parent.parent / "data" / "output" / "profiles.json"
CURATED = Path(__file__).resolve().parent.parent / "data" / "curated" / "status.json"
CURATED_KEYS = ("status", "text", "date", "document", "source", "checked")
PROFILE_VERSION = "p1"
MAX_RECORDS = 80
FIELDS = ("ai_policy", "ai_body", "funding", "infrastructure")
STATUSES = ("done", "announced", "none")
# Which records each state's prompt sees: the types that can bear on the four cells.
RELEVANT = {"Strategy & policy", "Regulation & ethics", "Governance bodies", "Funding & budget",
            "Infrastructure"}

PROMPT = """You fill one row of a table of Indian state governments' AI policy, using ONLY
the news records given (ID | date | stage | headline - first sentence). Four cells:

- "ai_policy": a state policy, mission, strategy or framework whose main subject is AI
  (AI together with other emerging tech counts). A general IT, GCC, startup or semiconductor
  policy that merely mentions AI does NOT count.
- "ai_body": a dedicated AI body set up by the state: AI mission office, task force, committee,
  AI department or cell, or a department renamed for AI.
- "funding": state government money for AI: a budget line, fund, grant or sanctioned amount.
  Company investment pledges, even in an MoU with the state, do NOT count.
- "infrastructure": state-backed AI infrastructure: an AI centre of excellence, AI lab or
  institute, compute facility, or AI data centre the state set up, funded or approved.

For each cell give:
- "status": "done" if the records say it was adopted, approved, released, set up, allocated,
  built or opened; "announced" if only planned, proposed, promised, drafted or under
  consideration; "none" if the records show nothing that qualifies.
- "text": at most 14 words naming the thing (with year or amount when the records give them),
  e.g. "Karnataka AI Policy 2026 approved by cabinet" or "Rs 500 crore AI fund in 2026-27 budget".
  Empty when status is "none".
- "cites": the record IDs that support it (1-3). Empty when status is "none".
If several things qualify, describe the most advanced and most significant one.
Return JSON: {"ai_policy": {...}, "ai_body": {...}, "funding": {...}, "infrastructure": {...}}"""

EMPTY = {"status": "none", "text": "", "cites": []}


def _input(records: list[dict]) -> list[str]:
    rel = [r for r in records if RELEVANT & set(r["tags"])]
    by_date = sorted(rel, key=lambda r: r["date"] or "", reverse=True)
    top = sorted(by_date, key=lambda r: -r["n_sources"])[:MAX_RECORDS]
    lines = []
    for r in sorted(top, key=lambda r: r["date"] or ""):
        summary = f" - {r['summary']}" if r.get("summary_source") == "publisher standfirst" else ""
        lines.append(f"{r['record_id']} | {r['date']} | {r.get('stage') or '?'} | {r['title']}{summary}")
    return lines


def _clean(answer: dict, valid: set[str]) -> dict:
    row = {}
    for field in FIELDS:
        cell = answer.get(field) if isinstance(answer.get(field), dict) else {}
        status = cell.get("status") if cell.get("status") in STATUSES else "none"
        cites = [c for c in cell.get("cites") or [] if isinstance(c, str) and c in valid][:3]
        text = re.sub(r"\s+", " ", str(cell.get("text") or "")).strip()
        row[field] = {"status": status, "text": text, "cites": cites} if status != "none" and cites and text else dict(EMPTY)
    return row


def apply_curated(profiles: dict[str, dict], path: Path = CURATED) -> dict[str, dict]:
    """profiles with the hand-checked cells in place of the model's."""
    if not path.exists():
        return profiles
    curated = json.loads(path.read_text(encoding="utf-8"))
    out = {s: dict(p) for s, p in profiles.items()}
    for state, cells in curated.items():
        if state.startswith("_"):
            continue
        for field, cell in cells.items():
            if field in FIELDS and cell.get("status") in ("done", "announced", "none"):
                out.setdefault(state, {})[field] = {"cites": [], "curated": True,
                                                    **{k: cell[k] for k in CURATED_KEYS if cell.get(k)}}
    return out


def load() -> dict[str, dict]:
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}


def build(records: list[dict]) -> dict[str, dict]:
    """state -> {field: {status, text, cites}, model, input_hash, generated_at}."""
    store = load()
    key, model, base = llm.config()
    if not key:
        print("profiles: no API key, keeping stored profiles")
        return store
    session = llm.make_session(key)
    made = 0
    for state in sorted({r["state"] for r in records}):
        lines = _input([r for r in records if r["state"] == state])
        digest = hashlib.sha1((PROFILE_VERSION + "\n".join(lines)).encode()).hexdigest()[:12]
        if store.get(state, {}).get("input_hash") == digest:
            continue
        if lines:
            try:
                answer = llm.chat_json(session, base, model, PROMPT,
                                       f"State: {state}\nRecords:\n" + "\n".join(lines))
            except Exception as e:  # keep the previous row rather than fail the run
                print(f"  {state}: failed ({type(e).__name__})")
                continue
            time.sleep(4.5)  # free-tier requests per minute
        else:
            answer = {}
        row = _clean(answer, {ln.split(" | ")[0] for ln in lines})
        store[state] = {**row, "model": model if lines else "", "input_hash": digest,
                        "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes")}
        made += 1
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"profiles: {made} built, {len(store)} stored")
    return store
