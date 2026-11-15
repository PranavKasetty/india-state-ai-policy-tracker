"""The writing model (profiles and briefs) is set apart from the labelling model.

Run:  python -m unittest tests.test_llm_writing
"""
import os
import unittest
from unittest import mock

from pipeline import llm


class WritingModelTests(unittest.TestCase):
    def test_writing_model_is_separate_and_overridable(self):
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "k", "LLM_MODEL": "label-model"}, clear=False):
            os.environ.pop("LLM_WRITING_MODEL", None)
            self.assertEqual(llm.config()[1], "label-model")
            self.assertEqual(llm.writing_config()[1], llm.DEFAULT_WRITING_MODEL)
            os.environ["LLM_WRITING_MODEL"] = "other"
            self.assertEqual(llm.writing_config()[1], "other")

    def test_budget_runs_out(self):
        with mock.patch.object(llm, "_writing_spent", 0), mock.patch.object(llm, "WRITING_BUDGET", 2):
            self.assertEqual([llm.writing_call_allowed() for _ in range(3)], [True, True, False])


if __name__ == "__main__":
    unittest.main()
