"""Hand-checked corrections to the state status table (data/curated/status.json).

Run:  python -m unittest tests.test_curated_status
"""
import json
import tempfile
import unittest
from pathlib import Path

from pipeline import pages, profiles

MODEL = {"Jharkhand": {"ai_policy": {"status": "done", "text": "Jharkhand AI Policy 2026 approved", "cites": ["R1"]},
                       "funding": {"status": "none", "text": "", "cites": []}}}


def curated(entries: dict) -> Path:
    path = Path(tempfile.mkdtemp()) / "status.json"
    path.write_text(json.dumps({"_about": "x", **entries}), encoding="utf-8")
    return path


class ApplyCurated(unittest.TestCase):
    def test_replaces_the_models_cell_and_keeps_the_others(self):
        path = curated({"Jharkhand": {"ai_policy": {"status": "announced", "text": "Draft policy", "date": "2026-07",
                                                    "source": "https://example.com/r", "checked": ""}}})
        out = profiles.apply_curated(MODEL, path)
        self.assertEqual(out["Jharkhand"]["ai_policy"], {"cites": [], "curated": True, "status": "announced",
                                                         "text": "Draft policy", "date": "2026-07",
                                                         "source": "https://example.com/r"})
        self.assertEqual(out["Jharkhand"]["funding"], MODEL["Jharkhand"]["funding"])
        self.assertEqual(MODEL["Jharkhand"]["ai_policy"]["status"], "done")  # input left alone

    def test_adds_a_state_the_model_had_nothing_for(self):
        path = curated({"Telangana": {"ai_policy": {"status": "done", "text": "AI Framework", "document": "https://x/f.pdf"}}})
        self.assertEqual(profiles.apply_curated({}, path)["Telangana"]["ai_policy"]["document"], "https://x/f.pdf")

    def test_ignores_unknown_markers_and_statuses(self):
        path = curated({"Goa": {"ai_vibes": {"status": "done", "text": "x"}, "funding": {"status": "maybe", "text": "x"}}})
        self.assertEqual(profiles.apply_curated({}, path), {})

    def test_the_committed_file_is_valid(self):
        data = json.loads(profiles.CURATED.read_text(encoding="utf-8"))
        for state, cells in data.items():
            if state.startswith("_"):
                continue
            for field, cell in cells.items():
                self.assertIn(field, profiles.FIELDS, state)
                self.assertIn(cell["status"], ("done", "announced", "none"), state)
                self.assertTrue(cell.get("document") or cell.get("source"), f"{state}: no link")

    def test_state_page_links_the_document(self):
        cells = profiles.apply_curated({}, curated({"Telangana": {"ai_policy": {"status": "done", "text": "AI Framework",
                                                                                "document": "https://x/f.pdf"}}}))
        html = pages._status_rows(cells["Telangana"], lambda c: f"#{c}")
        self.assertIn('<a class="st-doc" href="https://x/f.pdf" rel="noopener">Government document</a>', html)
        self.assertNotIn("[]", html)


if __name__ == "__main__":
    unittest.main()
