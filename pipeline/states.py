"""State normalisation.

Two jobs:
  normalize_state(value) -> canonical name for a *field value* ("UP", "Uttar-Pradesh",
                            "uttar pradesh" all -> "Uttar Pradesh").
  find_states(text)      -> which states a *headline* refers to, and on what evidence.

Free text is harder than field values: "AP" can mean Associated Press and "UP" can be
a verb in an all-caps headline. So abbreviations are only matched case-sensitively in
running text, and city names count as weaker evidence than the state's own name.
"""
import re

from .agencies import AGENCIES

# Canonical name -> (code, aliases). Codes follow ISO 3166-2:IN.
# Aliases are compared after _key() normalisation, so case, hyphens, dots and extra
# spaces do not need separate entries.
STATES: dict[str, tuple[str, list[str]]] = {
    "Andhra Pradesh":    ("AP", ["andhra", "a p"]),
    "Arunachal Pradesh": ("AR", []),
    "Assam":             ("AS", []),
    "Bihar":             ("BR", []),
    "Chhattisgarh":      ("CT", ["chattisgarh", "chhatisgarh"]),
    "Goa":               ("GA", []),
    "Gujarat":           ("GJ", ["gujrat"]),
    "Haryana":           ("HR", []),
    "Himachal Pradesh":  ("HP", ["himachal"]),
    "Jharkhand":         ("JH", []),
    "Karnataka":         ("KA", []),
    "Kerala":            ("KL", ["keralam"]),
    "Madhya Pradesh":    ("MP", []),
    "Maharashtra":       ("MH", []),
    "Manipur":           ("MN", []),
    "Meghalaya":         ("ML", []),
    "Mizoram":           ("MZ", []),
    "Nagaland":          ("NL", []),
    "Odisha":            ("OD", ["orissa"]),
    "Punjab":            ("PB", []),
    "Rajasthan":         ("RJ", []),
    "Sikkim":            ("SK", []),
    "Tamil Nadu":        ("TN", ["tamilnadu", "t n"]),
    "Telangana":         ("TG", ["telengana", "t gana", "ts"]),
    "Tripura":           ("TR", []),
    "Uttar Pradesh":     ("UP", ["uttarpradesh", "u p"]),
    "Uttarakhand":       ("UK", ["uttaranchal"]),
    "West Bengal":       ("WB", []),
    # Union territories with legislatures - included so they normalise cleanly,
    # even if the pipeline does not target them.
    "Delhi":             ("DL", ["nct of delhi"]),
    "Jammu and Kashmir": ("JK", ["jammu kashmir", "j k", "j and k"]),
    "Puducherry":        ("PY", ["pondicherry"]),
}

# Abbreviations matched in running text: case-sensitive regexes, ignored in all-caps
# headlines. Deliberately short list: "MP" (Member of Parliament), "AS", "GA", "PB"
# etc. are too ambiguous to trust in a headline.
TEXT_ABBREVIATIONS = {
    r"UP|U\.P\.": "Uttar Pradesh",
    r"TN": "Tamil Nadu",
    r"AP": "Andhra Pradesh",
    r"TG": "Telangana",
    r"WB": "West Bengal",
    r"J&K": "Jammu and Kashmir",
    # "Maha govt" is common shorthand, but "Maha Kumbh" (held in UP) is not Maharashtra.
    r"Maha(?= (?:govt|government|cabinet|CM|minister))": "Maharashtra",
}

# Phrases removed before matching, because they contain a state name without
# referring to that state's government.
MASK_PHRASES = ["new delhi", "bay of bengal"]

# Capital / major tech cities -> state. Weaker evidence: a Bengaluru company is not the
# Karnataka government. Used only when no state name appears in the headline.
CITIES = {
    "hyderabad": "Telangana", "bengaluru": "Karnataka", "bangalore": "Karnataka",
    "mysuru": "Karnataka", "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu",
    "mumbai": "Maharashtra", "pune": "Maharashtra", "nagpur": "Maharashtra",
    "lucknow": "Uttar Pradesh", "noida": "Uttar Pradesh", "bhubaneswar": "Odisha",
    "amaravati": "Andhra Pradesh", "visakhapatnam": "Andhra Pradesh", "vizag": "Andhra Pradesh",
    "thiruvananthapuram": "Kerala", "kochi": "Kerala", "gandhinagar": "Gujarat",
    "ahmedabad": "Gujarat", "kolkata": "West Bengal", "jaipur": "Rajasthan",
    "bhopal": "Madhya Pradesh", "indore": "Madhya Pradesh", "patna": "Bihar",
    "gurugram": "Haryana", "chandigarh": "Punjab", "guwahati": "Assam",
    # Capitals of the states added on 2026-11-01 (weakest evidence, used only when no name matches)
    "raipur": "Chhattisgarh", "ranchi": "Jharkhand", "dehradun": "Uttarakhand", "shimla": "Himachal Pradesh",
    "panaji": "Goa", "shillong": "Meghalaya", "aizawl": "Mizoram", "kohima": "Nagaland", "imphal": "Manipur",
    "itanagar": "Arunachal Pradesh", "agartala": "Tripura", "gangtok": "Sikkim", "dispur": "Assam",
}


def _key(s: str) -> str:
    """Lowercase, turn punctuation into spaces, collapse whitespace."""
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_LOOKUP = {_key(v): name for name, (code, aliases) in STATES.items() for v in [name, code, *aliases]}
_LOOKUP[_key("J&K")] = "Jammu and Kashmir"


def normalize_state(value: object) -> str | None:
    """Map a state field value to its canonical name. Returns None if unrecognised."""
    return None if value is None else _LOOKUP.get(_key(str(value)))


def state_code(name: str) -> str | None:
    return STATES[name][0] if name in STATES else None


# Full names and multi-word aliases, longest first so "Andhra Pradesh" wins over "Andhra".
_NAME_PATTERNS = sorted(
    ((v, n) for n, (_c, al) in STATES.items() for v in [n, *al] if len(v) > 3),
    key=lambda p: -len(p[0]),
)


# Pakistan also has a Punjab, with its own government AI programmes.
FOREIGN_MARKERS = {
    "Punjab": re.compile(r"pakistan|lahore|rawalpindi|faisalabad|multan|maryam nawaz|\bPITB\b", re.I),
}

# Agency names are proper nouns: match case-sensitively on the raw text, otherwise
# "Invest UP" matches "invest up to 1 billion".
_AGENCY_PATTERNS = [(rf"(?<![\w-]){re.escape(a)}(?![\w-])", s)
                    for s, names in AGENCIES.items() for a in names]


def find_states(text: str) -> tuple[list[str], str | None]:
    """Return (states, evidence) for a headline.

    states   - canonical names in order of first appearance
    evidence - "name" (state name or alias), "agency" (a state body, see agencies.py),
               "abbrev" (e.g. "UP"), "city", or None
    """
    if not text:
        return [], None
    k = " " + _key(text) + " "
    for phrase in MASK_PHRASES:
        k = k.replace(f" {phrase} ", " # ")
    mostly_upper = sum(c.isupper() for c in text) > 0.6 * sum(c.isalpha() for c in text)

    # Strongest evidence first; stop at the first level that finds anything.
    levels = [
        ("name", k, [(f" {_key(v)} ", n) for v, n in _NAME_PATTERNS]),
        ("agency", text, _AGENCY_PATTERNS),
        ("abbrev", text, [] if mostly_upper else
            [(rf"(?<![A-Za-z])(?:{p})(?![A-Za-z])", n) for p, n in TEXT_ABBREVIATIONS.items()]),
        ("city", k, [(f" {c} ", n) for c, n in CITIES.items()]),
    ]
    for evidence, haystack, patterns in levels:
        hits: list[tuple[int, str]] = []
        for pattern, name in patterns:
            if evidence in ("abbrev", "agency"):
                m = re.search(pattern, haystack)
                pos = m.start() if m else -1
            else:
                pos = haystack.find(pattern)
            if pos >= 0 and not (name in FOREIGN_MARKERS and FOREIGN_MARKERS[name].search(text)):
                hits.append((pos, name))
        if hits:
            return list(dict.fromkeys(n for _, n in sorted(hits))), evidence
    return [], None
