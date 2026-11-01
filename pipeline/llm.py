"""Optional LLM judge: relevance + categories for candidate headlines.

Candidates are items whose headline names a covered state and an AI/robotics term.
The rules in classify.py decide everything else; the LLM applies the written
inclusion rubric below, which handles what keyword rules cannot (implied government
actors, statements vs actions, crime vs policy).

Any OpenAI-compatible endpoint works. Defaults to Gemini's free tier:
  LLM_API_KEY (or GOOGLE_API_KEY), LLM_MODEL, LLM_BASE_URL - from env or .env.
No key -> the pipeline uses rules only.

Labels are cached in data/raw/llm_labels.jsonl (committed) keyed by guid and
PROMPT_VERSION, so reruns are reproducible and the daily job only labels new items.
"""
import json
import os
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .classify import CATEGORY_IDS, SECTORS

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "raw" / "llm_labels.jsonl"
PAIRS = ROOT / "data" / "raw" / "llm_pairs.jsonl"
PROMPT_VERSION = "v2"  # v2: stricter on private actors, worked examples
BATCH = 40
DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-3.5-flash-lite"  # free tier: 15 RPM, 500 RPD; pinned for reproducibility

RUBRIC = f"""You label news headlines for a dataset of AI policy activity by Indian state governments.

IN SCOPE only when a state government body (department, minister, CM, police, district or
municipal body, state agency or PSU, state-run university) - or the central government in a way
tied to that specific state - is the ACTOR: it announces, funds, signs, deploys, regulates,
trains, hosts, approves or states a goal about AI or robotics. State-backed data centres,
state-hosted or state-endorsed events and state university courses count. Robotics counts even
without an AI mention. A CM/minister stating an AI goal or plan counts.

OUT OF SCOPE:
- a company, private university, startup, NGO or industry body acting alone, even inside the
  state (opening an office or centre, a launch, a talk, a survey, a report);
- a speech or event at a private institution, unless a state official announces something there;
- advice or exhortation with no government actor ("MSMEs urged to adopt AI");
- results or news about individuals (a student builds a robot, a professor wins an award);
- central-government actions with no specific state tie;
- crime stories (deepfake/fraud arrests, cases, fact-checks of AI videos); election politics
  and AI campaign videos; opinion pieces; foreign news (e.g. Pakistan's Punjab);
- stories where the state is only a location or birthplace.
If the headline does not show a government actor, and none is clearly implied, mark OUT.
When unsure, mark OUT.

Examples:
- "Telangana signs MoU with Google for AI skilling" -> IN (partnership, skilling)
- "Kerala police deploy AI cameras to catch traffic violations" -> IN (deployment)
- "Tamil Nadu CM says state will become AI hub by 2030" -> IN (strategy_policy)
- "IBM launches FutureNow Centre in Vizag" -> OUT (company acting alone)
- "IISc Director at Gujarat's Adani University: we should control AI" -> OUT (talk at a private university)
- "Gujarat MSMEs urged to embrace AI" -> OUT (no government actor)
- "Bengaluru startup raises $10 million for AI tool" -> OUT (private company)
- "Man held for AI deepfake of Maharashtra minister" -> OUT (crime story)

For in-scope headlines give:
- primary: the single main category id
- tags: every category id that applies (include primary)
- sector: one of {[*SECTORS, "Cross-cutting"]}
Category ids: {[c for c in CATEGORY_IDS.values() if c != "other"]}
  strategy_policy = policy, mission, roadmap, vision, stated goals
  governance_body = task force, committee, AI cell, agency, restructuring
  regulation_ethics = rules, guidelines, frameworks, mandates, ethics, data governance
  infrastructure = data centres, compute/GPUs, centres of excellence, AI parks/cities, labs
  partnership = MoU, pact, tie-up with a company, university or foundation
  deployment = AI used in a government service or operation
  funding_budget = budget allocation, fund, grant, investment commitment
  skilling = training officials/teachers/students, courses, curriculum
  events_outreach = summit, conclave, hackathon, challenge hosted or endorsed by the state

Return JSON: {{"labels": [{{"i": <number>, "in_scope": true|false, "reason": "<max 12 words>",
"primary": "<id or null>", "tags": [<ids>], "sector": "<sector or null>"}}]}} - one per headline."""


def _env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == name:
                return v.strip().strip('"').strip("'")
    return ""


def config() -> tuple[str, str, str]:
    key = _env("LLM_API_KEY") or _env("GOOGLE_API_KEY")
    return key, _env("LLM_MODEL") or DEFAULT_MODEL, _env("LLM_BASE_URL") or DEFAULT_BASE


def load_store() -> dict[str, dict]:
    if not STORE.exists():
        return {}
    with open(STORE, encoding="utf-8") as f:
        return {r["guid"]: r for r in map(json.loads, f) if r.get("prompt_version") == PROMPT_VERSION}


def make_session(key: str) -> requests.Session:
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {key}"
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=6, backoff_factor=5, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"], respect_retry_after_header=True)))
    return session


def chat_json(session: requests.Session, base: str, model: str, system: str, user: str) -> dict:
    resp = session.post(f"{base}/chat/completions", timeout=120, json={
        "model": model, "temperature": 0, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    resp.raise_for_status()
    return json.loads(resp.json()["choices"][0]["message"]["content"])


def _ask(session: requests.Session, base: str, model: str, system: str, user: str, field: str) -> list:
    """chat_json with one retry: free models occasionally return malformed JSON,
    or the bare list without the {field: [...]} wrapper."""
    for attempt in (1, 2):
        try:
            data = chat_json(session, base, model, system, user)
            return data if isinstance(data, list) else data[field]
        except (ValueError, KeyError, TypeError):
            if attempt == 2:
                raise


def _call(session: requests.Session, base: str, model: str, batch: list[dict]) -> list[dict]:
    lines = "\n".join(f"{i}. {it['title']} ({it['source_name']})" for i, it in enumerate(batch))
    return _ask(session, base, model, RUBRIC, lines, "labels")


def label(candidates: list[dict]) -> dict[str, dict]:
    """Label candidates not yet in the store. Returns guid -> label for all stored."""
    store = load_store()
    key, model, base = config()
    todo = [c for c in candidates if c["guid"] not in store]
    if not key:
        print("llm: no API key, using rules only")
        return store
    print(f"llm: {len(candidates) - len(todo)} cached, {len(todo)} to label with {model}")
    session = make_session(key)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(STORE, "a", encoding="utf-8") as f:
        for start in range(0, len(todo), BATCH):
            batch = todo[start:start + BATCH]
            try:
                labels = _call(session, base, model, batch)
            except (requests.RequestException, ValueError, KeyError, TypeError) as e:
                print(f"  batch {start // BATCH} failed ({type(e).__name__}); rules will cover it")
                continue
            for lab in labels:
                if not isinstance(lab.get("i"), int) or not 0 <= lab["i"] < len(batch):
                    continue
                row = {"guid": batch[lab["i"]]["guid"], "prompt_version": PROMPT_VERSION, "model": model,
                       **{k: lab.get(k) for k in ("in_scope", "reason", "primary", "tags", "sector")}}
                store[row["guid"]] = row
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  {min(start + BATCH, len(todo))}/{len(todo)}")
            time.sleep(4.5)  # stay under 15 requests per minute
    return store


PAIR_PROMPT = """Each line gives two news headlines about the same Indian state, published within a
week of each other. Answer whether they report the SAME development (one announcement, decision,
launch or event, possibly reworded or with different details), not merely the same topic.
Two different decisions by the same cabinet meeting are different developments.
Return JSON: {"same": [{"i": <number>, "same": true|false}]} - one per line."""
PAIR_BATCH = 50


def _pair_key(a: dict, b: dict) -> str:
    return "|".join(sorted((a["guid"], b["guid"])))


def same_development(pairs: list[tuple[dict, dict]]) -> list[bool | None]:
    """Judge near-duplicate headline pairs; None when unknown (no key or failed call).
    Verdicts are cached in data/raw/llm_pairs.jsonl."""
    cache = {}
    if PAIRS.exists():
        with open(PAIRS, encoding="utf-8") as f:
            cache = {r["pair"]: r["same"] for r in map(json.loads, f)}
    key, model, base = config()
    todo = [p for p in pairs if _pair_key(*p) not in cache]
    if key and todo:
        print(f"llm pairs: {len(pairs) - len(todo)} cached, {len(todo)} to judge")
        session = make_session(key)
        with open(PAIRS, "a", encoding="utf-8") as f:
            for start in range(0, len(todo), PAIR_BATCH):
                batch = todo[start:start + PAIR_BATCH]
                lines = "\n".join(f"{i}. A: {a['title']} || B: {b['title']}" for i, (a, b) in enumerate(batch))
                try:
                    verdicts = _ask(session, base, model, PAIR_PROMPT, lines, "same")
                except (requests.RequestException, ValueError, KeyError, TypeError) as e:
                    print(f"  pair batch {start // PAIR_BATCH} failed ({type(e).__name__})")
                    continue
                for v in verdicts:
                    if isinstance(v.get("i"), int) and 0 <= v["i"] < len(batch) and isinstance(v.get("same"), bool):
                        k = _pair_key(*batch[v["i"]])
                        cache[k] = v["same"]
                        f.write(json.dumps({"pair": k, "same": v["same"], "model": model}) + "\n")
                time.sleep(4.5)
    return [cache.get(_pair_key(a, b)) for a, b in pairs]
