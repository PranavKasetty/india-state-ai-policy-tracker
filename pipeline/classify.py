"""Stage 2 - relevance and classification (rule-based).

Inclusion rule (project decision): a record is in scope when a state government
body - or the central government in a way tied to a specific state - acts on AI or
robotics: announces, funds, signs, deploys, regulates, trains, hosts or endorses.
Private-sector news with no government actor is out.

Rules work on the headline only, so every decision carries a reason string and the
excluded items are exported for audit. An optional LLM pass (llm.py) can override
these decisions when an API key is configured.
"""
import re

from .states import find_states
from .terms import AI_RE

# --- relevance -----------------------------------------------------------------

GOV_ACTOR_RE = re.compile(
    r"\b(govt|government|minister|ministry|CM|chief minister|cabinet|department|dept|"
    r"policy|mission|MoU|pact|budget|assembly|task ?force|centre of excellence|CoE|police|"
    r"collector|district administration|municipal|panchayat|zilla|state[- ]run|"
    r"state[- ]owned|public sector|e-?governance|officials?|secretary|"
    r"IndiaAI|MeitY|NITI Aayog|Union govt|central govt)\b", re.IGNORECASE)
# Not included: bare "Centre" (matches "data centre") and "corporation" (companies).

# "<State> launches ...", "Kerala to set up ..." - the state itself is the actor.
STATE_ACTOR_VERBS = (r"(launch|sign|ink|unveil|roll|introduc|approv|announc|set|plan|partner|"
                     r"deploy|mandat|bet|tie|join|adopt|allocat|earmark|open|host|build|"
                     r"develop|creat|establish|propos|to |will |eye|aim|seek|use|train)")

EXCLUDE_RE = {
    "crime story (deepfake/fraud case)": re.compile(
        r"\b(arrest|booked|books|FIR|held for|nabbed|duped|cheated|morphed|extort|remand|"
        r"case against|AI[- ](generated )?(video|image|clip)s? (of|linking|showing)|"
        r"(deepfake|fake|viral) (AI )?(video|image|clip))", re.I),
    "politics, not policy": re.compile(
        r"\b(poll campaign|election campaign|BJP|Congress|AAP|DMK|TVK|TMC|YSRCP|BRS)\b.*\b(deepfake|AI video|AI-generated)", re.I),
    "opinion / explainer": re.compile(r"^(opinion|editorial|explained|analysis|view)\b|\| opinion", re.I),
    "foreign": re.compile(r"\bpakistan|lahore|maryam nawaz|\bUK\b|Britain|Azerbaijan|-born\b", re.I),
}


def relevance(title: str, covered: list[str]) -> tuple[bool, str, str, str]:
    """Return (in_scope, reason, state, state_evidence)."""
    states, evidence = find_states(title)
    states = [s for s in states if s in covered]
    if not states:
        return False, "no covered state in headline", "", ""
    state = states[0]
    if not AI_RE.search(title):
        return False, "no AI/robotics term in headline", state, evidence or ""
    for reason, rx in EXCLUDE_RE.items():
        if rx.search(title):
            return False, reason, state, evidence or ""
    starts_with_state = re.match(rf"^\W*{re.escape(state)}\W+{STATE_ACTOR_VERBS}", title, re.I)
    if evidence == "agency" or GOV_ACTOR_RE.search(title) or starts_with_state:
        return True, "government actor + AI", state, evidence or ""
    return False, "no government actor in headline", state, evidence or ""


# --- categories (multi-label tags, one primary) ----------------------------------

# Order = priority for the primary category: the most policy-significant tag wins.
CATEGORIES = {
    # Includes stated intent ("to emerge as AI hub", "pushes AI") - CM/minister statements.
    "Strategy & policy": r"\bpolic(y|ies)\b|\bAI mission\b|strategy|roadmap|vision|blueprint|action plan|"
                         r"\b(emerge|hub|push(es)?|focus|aims?|eyes|bets?|expand|cooperation|warns?|adoption)\b",
    "Regulation & ethics": r"regulat|guideline|framework|ethic|\brules?\b|mandatory|\bban\b|privacy|standard|deepfake",
    "Governance bodies": r"task ?force|committee|council|advisory|\bboard\b|agenc(y|ies)|directorate|\bcell\b|panel|authority|rejig",
    "Funding & budget": r"budget|crore|allocat|\bfund|grant|invest|₹|\bRs\.?\b|\$|billion|lakh",
    "Infrastructure": r"data cent(re|er)|compute|GPU|supercomput|AI (city|park|hub|valley|university)|centre of excellence|\bCoE\b|incubat|\blab\b|cluster",
    "Partnership / MoU": r"\bMoU\b|\bpact\b|partner|tie[- ]?up|join hands|collaborat|agreement|\binks?\b|\bsigns?\b",
    "Deployment": r"\blaunch|deploy|roll(s|ed)? out|introduc|AI[- ](based|powered|enabled|driven|led)|\bpilot\b|\buses?\b|using|chatbot|"
                  r"turn to|activat|camera|tool|platform|system",
    "Skilling": r"train|skill|course|curriculum|literacy|fellowship|academy|teacher",
    "Events & outreach": r"summit|conclave|conference|hackathon|expo|workshop|challenge",
}
SECTORS = {
    "Health": r"health|hospital|medical|doctor|patient|disease|\bTB\b|cancer|AIIMS",
    "Agriculture": r"farm|agri|crop|kisan|soil|fisher|livestock|dairy",
    "Education": r"school|education|teacher|student|universit|college|exam|classroom",
    "Policing & safety": r"police|crime|cyber|surveillance|CCTV|law and order|jail|prison|traffic violation",
    "Urban & transport": r"traffic|metro|transport|\bbus|road|urban|municipal|smart city|pothole",
    "Revenue & citizen services": r"citizen|grievance|land|revenue|tax|GST|portal|certificate|ration|welfare|WhatsApp",
    "Industry & startups": r"startup|industr|MSME|jobs|investment|IT sector|company|companies|data cent",
}
CATEGORY_IDS = {
    "Strategy & policy": "strategy_policy", "Regulation & ethics": "regulation_ethics",
    "Governance bodies": "governance_body", "Funding & budget": "funding_budget",
    "Infrastructure": "infrastructure", "Partnership / MoU": "partnership",
    "Deployment": "deployment", "Skilling": "skilling", "Events & outreach": "events_outreach",
    "Other": "other",
}
CATEGORY_LABELS = {v: k for k, v in CATEGORY_IDS.items()}
_CAT_RES = {k: re.compile(v, re.I) for k, v in CATEGORIES.items()}
_SEC_RES = {k: re.compile(v, re.I) for k, v in SECTORS.items()}


def categorise(title: str) -> tuple[str, list[str], str]:
    """Return (primary_category, tags, sector)."""
    tags = [k for k, rx in _CAT_RES.items() if rx.search(title)] or ["Other"]
    sector = next((k for k, rx in _SEC_RES.items() if rx.search(title)), "Cross-cutting")
    return tags[0], tags, sector
