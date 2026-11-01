"""AI and government vocabulary, shared by search queries and headline filters.

The query strings decide what Google returns; the regexes decide what we keep.
Keep the two lists in step when editing.
"""
import re

# "GenAI" is listed separately because Google treats it as one token, not "AI".
# Robotics is in scope even without an AI mention (project decision).
AI_QUERY = ('AI OR "artificial intelligence" OR GenAI OR "generative AI" OR agentic OR LLM OR '
            '"machine learning" OR chatbot OR robotics OR robot')

# "AI" (but not Air India flight numbers like "AI-171") plus terms that often appear
# without the word AI. "chatbot"/"bot" also catch some rule-based bots; the relevance
# step decides those. "model" alone is excluded: in a sample of cached headlines every
# extra hit was noise ("role model", "model schools").
AI_RE = re.compile(
    r"\bAI\b(?![- ]?\d)|artificial intelligence|\bGenAI\b|generative|agentic|\bLLMs?\b|"
    r"language model|foundation model|machine learning|deep learning|neural network|"
    r"computer vision|chatbot|\bbots?\b|robot", re.IGNORECASE)

GOV_QUERY = "government OR govt OR minister OR policy OR MoU"

# Rough government signal. Used to rank states in the scan, not to decide inclusion.
GOV_RE = re.compile(
    r"\b(govt|government|minister|CM|chief minister|cabinet|department|policy|mission|"
    r"MoU|pact|budget|task force|centre of excellence|police|collector|municipal)\b",
    re.IGNORECASE)
