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
PROMPT_VERSION = "v1"
BATCH = 40
DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_MODEL = "gemini-3.5-flash-lite"  # free tier: 15 RPM, 500 RPD; pinned for reproducibility

RUBRIC = f"""You label news headlines for a dataset of AI policy activity by Indian state governments.

IN SCOPE when a state government body (department, minister, CM, police, municipal body,
state agency, state university) - or the central government in a way tied to that specific
state - acts on AI or robotics: announces, funds, signs, deploys, regulates, trains, hosts
or endorses. State-backed data centres, state-endorsed conferences and state university
courses count. Robotics counts even without an AI mention. A CM/minister stating an AI
goal or vision counts.

OUT OF SCOPE: private-company news with no government actor; central-government actions
with no specific state tie; crime stories (deepfake/fraud arrests, cases, fact-checks of
AI videos); election politics and AI campaign videos; opinion pieces; foreign news
(e.g. Pakistan's Punjab); stories where the state is only a location or birthplace.

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


def _call(session: requests.Session, base: str, model: str, batch: list[dict]) -> list[dict]:
    lines = "\n".join(f"{i}. {it['title']} ({it['source_name']})" for i, it in enumerate(batch))
    return chat_json(session, base, model, RUBRIC, lines)["labels"]


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
            except (requests.RequestException, ValueError, KeyError) as e:
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
