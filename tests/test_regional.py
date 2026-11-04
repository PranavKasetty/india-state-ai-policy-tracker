"""Hindi and Marathi news (pipeline/regional.py) and how it joins the English records.

Run:  python -m unittest tests.test_regional
"""
import unittest
from unittest import mock

from pipeline import regional, run

ITEM = {"guid": "g1", "title": "यूपी में एआई से होगी खनन की निगरानी", "source_name": "Amar Ujala",
        "gnews_url": "https://news.google.com/x", "published_raw": "Mon, 05 Oct 2026 04:00:00 GMT",
        "lang": "hi", "state_queried": "Uttar Pradesh"}
LABEL = {"guid": "g1", "in_scope": True, "english": "UP to monitor mining with AI", "state": "Uttar Pradesh",
         "primary": "deployment", "tags": ["deployment"], "sector": "Policing & safety"}


def classify(item: dict, label: dict | None):
    with mock.patch.object(regional, "load", return_value={item["guid"]: item}), \
         mock.patch.object(regional, "load_labels", return_value={item["guid"]: label} if label else {}):
        return regional.classify("2025-11-01", False, ["Uttar Pradesh", "Bihar"], run.source_reason)


class Candidate(unittest.TestCase):
    def test_needs_an_ai_term_in_the_original(self):
        self.assertTrue(regional.candidate(ITEM))
        self.assertFalse(regional.candidate({**ITEM, "title": "यूपी में खनन की निगरानी"}))

    def test_english_headlines_in_the_regional_edition_are_left_to_the_english_pipeline(self):
        self.assertFalse(regional.candidate({**ITEM, "title": "UP to use AI against illegal mining"}))


class Classify(unittest.TestCase):
    def test_in_scope_item_becomes_an_english_candidate(self):
        kept, excluded = classify(ITEM, LABEL)
        self.assertEqual(excluded, [])
        r = kept[0]
        self.assertEqual((r["title"], r["title_original"], r["language"]), (LABEL["english"], ITEM["title"], "hi"))
        self.assertEqual((r["state"], r["primary_category"], r["date"]), ("Uttar Pradesh", "Deployment", "2026-10-05"))

    def test_item_about_another_state_is_excluded(self):
        kept, excluded = classify(ITEM, {**LABEL, "state": "Madhya Pradesh"})
        self.assertEqual(kept, [])
        self.assertIn("about Madhya Pradesh", excluded[0]["reason"])

    def test_unlabelled_item_waits(self):
        kept, excluded = classify(ITEM, None)
        self.assertEqual((kept, excluded[0]["reason"]), ([], "regional: not yet labelled"))


class Records(unittest.TestCase):
    def test_merged_record_keeps_its_english_headline_and_earliest_date(self):
        hindi = {"guid": "h", "title": "UP to monitor mining with AI", "date": "2026-10-04", "date_precision": "day",
                 "source_name": "Amar Ujala", "gnews_url": "", "state": "Uttar Pradesh", "language": "hi",
                 "title_original": ITEM["title"]}
        english = {**hindi, "guid": "e", "date": "2026-10-05", "source_name": "TOI", "language": "en", "title_original": ""}
        records, sources, _ = run.build_records([hindi, english], use_llm=False)
        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual((r["guid"], r["language"], r["date"]), ("e", "en", "2026-10-04"))
        self.assertEqual(r["also_reported_by"], ["Amar Ujala"])
        self.assertEqual({s["language"] for s in sources}, {"hi", "en"})


if __name__ == "__main__":
    unittest.main()
