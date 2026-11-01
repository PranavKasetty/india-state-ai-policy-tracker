"""State government bodies that work on AI, per covered state.

Used two ways:
  1. as extra search queries, to find stories that name the body but never say
     "government" or the state's name ("GHMC deploys AI cameras");
  2. as evidence in states.find_states: naming the body ties a headline to its state.

Compiled from web searches on 2026-11-01 (sources listed in the README). Acronyms that
collide with common words or other entities are given only by full name: MARVEL
(comics), RTGS (bank transfers), KITE, TASK, BMC (Mumbai and Bhubaneswar).
Technopark/Infopark were dropped after matching a story about Azerbaijan.
Matching is case-sensitive (names are proper nouns; "Invest UP" vs "invest up to").
"""

AGENCIES: dict[str, list[str]] = {
    "Andhra Pradesh": [
        "Real Time Governance Society", "APIIC", "Amaravati Quantum Valley", "Mana Mitra",
    ],
    "Bihar": [
        "BELTRON", "Bihar AI Mission", "Bihar Artificial Intelligence Mission", "Startup Bihar",
    ],
    "Gujarat": [
        "Gujarat Informatics", "GUJCOST", "i-Hub Gujarat", "GIFT City", "IAIRO",
        "Indian AI Research Organisation", "Ahmedabad Municipal Corporation",
        "Surat Municipal Corporation",
    ],
    "Karnataka": [
        "KDEM", "Karnataka Digital Economy Mission", "Greater Bengaluru Authority", "BBMP",
        "KEONICS", "Bengaluru Tech Summit",
    ],
    "Kerala": [
        "KSUM", "Kerala Startup Mission", "Kerala State IT Mission", "KSITM",
        "Digital University Kerala", "K-DISC", "Kerala Infrastructure and Technology for Education",
        "KELTRON", "Cyberdome",
    ],
    "Maharashtra": [
        "Maharashtra Research and Vigilance for Enhanced Law Enforcement", "MahaCrimeOS",
        "MahaIT", "MIDC", "Brihanmumbai Municipal Corporation", "Pune Municipal Corporation",
        "Maharashtra State Innovation Society",
    ],
    "Odisha": [
        "OCAC", "Odisha Computer Application Centre", "Odisha AI Mission", "Startup Odisha",
        "Bhubaneswar Municipal Corporation", "IDCO",
    ],
    "Punjab": [
        "Punjab Artificial Intelligence System", "PSeGS", "Punjab State e-Governance Society",
        "Invest Punjab",
    ],
    "Tamil Nadu": [
        "TNeGA", "Tamil Nadu e-Governance Agency", "iTNT", "ELCOT", "StartupTN", "TNAIM",
        "Tamil Nadu AI Mission", "Greater Chennai Corporation", "Guidance Tamil Nadu", "TIDCO",
    ],
    "Telangana": [
        "T-Hub", "T-Works", "WE Hub", "Telangana Academy for Skill and Knowledge",
        "Telangana AI Mission", "T-AIM", "TGDeX", "Telangana Data Exchange", "GHMC",
        "Telangana AI Innovation Hub", "Aikam", "TGIIC", "Young India Skills University",
    ],
    "Uttar Pradesh": [
        "UPDESCO", "UP Electronics Corporation", "UPLC", "Invest UP", "Lucknow AI City",
        "YEIDA", "Yamuna Expressway Industrial Development Authority",
    ],
}
