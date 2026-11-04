"""How far each development has gone: announced, decided or underway (LLM, cached).

A separate pass from the in/out rubric (llm.py), so adding it does not change which
records are in the dataset. It reads the headline and, when enrichment found one,
the publisher's standfirst. Answers are cached in data/raw/llm_stages.jsonl by the
record's earliest-report guid and STAGE_VERSION, so reruns cost nothing and only
new records are sent.

  announced  plans, proposals, promises, speeches, goals, "will", "to", "mulls"
  decided    formally adopted but not yet running: approved, notified, signed,
             allocated, constituted, tendered
  underway   running or done: launched, deployed, in use, held, inaugurated, trained
"""
import json
import time
from pathlib import Path

import requests

from . import llm

STORE = Path(__file__).resolve().parent.parent / "data" / "raw" / "llm_stages.jsonl"
STAGE_VERSION = "s1"
STAGES = ("announced", "decided", "underway")
LABELS = {"announced": "Announced or planned", "decided": "Approved or signed", "underway": "Launched or in use"}

PROMPT = """Each line is a news report about an Indian state government's AI or robotics
activity: a headline, sometimes followed by " -- " and the article's first sentence.
Say how far the reported action has gone:
- "announced": an intention, plan, proposal, promise, speech, stated goal, review meeting,
  draft, or anything that "will", "to", "set to", "plans", "mulls", "eyes", "proposes",
  "considers" or "urges". Also an official praising, pitching or inviting investment.
- "decided": a formal decision that is not yet running: a policy approved, released or
  notified; a cabinet nod; an order, rule or guideline issued; money allocated or sanctioned;
  an MoU, agreement or contract signed; a body constituted or appointed; a tender issued;
  a foundation stone laid.
- "underway": now running or done: a service, tool, system or scheme launched, deployed or
  in use; results of a deployment; training or a course delivered or started; an event,
  summit or hackathon held; a facility inaugurated or opened.
Judge what the report says has happened, not what is promised next. If several things are
reported, take the most advanced stage the report states as done.
Examples:
- "Telangana to set up AI city near Hyderabad" -> announced
- "Cabinet approves Maharashtra AI policy 2026" -> decided
- "Odisha signs MoU with Sarvam AI" -> decided
- "Kerala police deploy AI cameras on highways" -> underway
- "AI cameras catch 2,000 helmet violators in Lucknow" -> underway
- "CM Naidu says AI will transform governance" -> announced
Return JSON: {"stages": [{"i": <number>, "stage": "announced"|"decided"|"underway"}]} - one per line."""


def load_store() -> dict[str, str]:
    if not STORE.exists():
        return {}
    with open(STORE, encoding="utf-8") as f:
        return {r["guid"]: r["stage"] for r in map(json.loads, f) if r.get("stage_version") == STAGE_VERSION}


def _line(r: dict) -> str:
    text = r["title"]
    if r.get("summary_source") == "publisher standfirst" and r.get("summary"):
        text += " -- " + r["summary"][:300]
    return text.replace("\n", " ")


def label(records: list[dict]) -> dict[str, str]:
    """Stage every record not yet in the store. Returns guid -> stage for all stored."""
    store = load_store()
    todo = [r for r in records if r["guid"] not in store]
    key, model, base = llm.config()
    if not todo:
        return store
    if not key:
        print(f"stage: no API key, {len(todo)} records left without a stage")
        return store
    print(f"stage: {len(records) - len(todo)} cached, {len(todo)} to label with {model}")
    session = llm.make_session(key)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(STORE, "a", encoding="utf-8") as f:
        for start in range(0, len(todo), llm.BATCH):
            batch = todo[start:start + llm.BATCH]
            lines = "\n".join(f"{i}. {_line(r)}" for i, r in enumerate(batch))
            try:
                answers = llm._ask(session, base, model, PROMPT, lines, "stages")
            except (requests.RequestException, ValueError, KeyError, TypeError) as e:
                print(f"  batch {start // llm.BATCH} failed ({type(e).__name__}); left without a stage")
                continue
            for a in answers:
                i, stage = a.get("i"), a.get("stage")
                if isinstance(i, int) and 0 <= i < len(batch) and stage in STAGES:
                    store[batch[i]["guid"]] = stage
                    f.write(json.dumps({"guid": batch[i]["guid"], "stage_version": STAGE_VERSION,
                                        "model": model, "stage": stage}, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  {min(start + llm.BATCH, len(todo))}/{len(todo)}")
            time.sleep(4.5)  # stay under 15 requests per minute
    return store
