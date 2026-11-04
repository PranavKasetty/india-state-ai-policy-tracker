"""Recovering headlines that reached us cut short (pipeline/enrich.py).

Run:  python -m unittest tests.test_enrich_titles
"""
import unittest

from pipeline.enrich import full_headline, looks_cut

CUT = "Human intelligence must guide AI in governance, says Jitendra Singh; Jaipur Declaration adopted at National e"
URL = ("https://ddnews.gov.in/en/human-intelligence-must-guide-ai-in-governance-says-jitendra-singh-"
       "jaipur-declaration-adopted-at-national-e-governance-conference/")
PAGE = (f"<title>{CUT} | DD News</title><h1>DD News</h1>"
        f"<h2>{CUT}-Governance Conference</h2><script>{{\"headline\": \"{CUT}-Governance Conference\"}}</script>")


class LooksCut(unittest.TestCase):
    def test_slug_that_carries_on_mid_word(self):
        self.assertTrue(looks_cut(CUT, URL))

    def test_slug_that_ends_with_the_headline(self):
        self.assertFalse(looks_cut("Jaipur Declaration adopted at National e-Governance Conference", URL))

    def test_ellipsis(self):
        self.assertTrue(looks_cut("CM discusses student wel..", "https://example.com/article/123"))

    def test_url_without_a_slug_says_nothing(self):
        self.assertFalse(looks_cut(CUT, "https://example.com/article/123"))


class FullHeadline(unittest.TestCase):
    def test_takes_the_longer_headline_from_the_page(self):
        self.assertEqual(full_headline(PAGE, CUT), CUT + "-Governance Conference")

    def test_finishes_a_headline_cut_with_an_ellipsis(self):
        page = "<h1>CM meets students; discusses student welfare and visas</h1>"
        self.assertEqual(full_headline(page, "CM meets students; discusses student wel.."),
                         "CM meets students; discusses student welfare and visas")

    def test_does_not_extend_a_complete_headline_into_body_text(self):
        page = "<p>Kerala launches AI mission to improve services across districts.</p>"
        self.assertEqual(full_headline(page, "Kerala launches AI mission"), "")

    def test_page_whose_copy_is_cut_too(self):
        page = "<h1>Citizens will get one-click access to laws, reso...</h1>"
        self.assertEqual(full_headline(page, "Citizens will get one-click access to laws, reso..."), "")

    def test_stops_at_json_escapes(self):
        page = '<script>{"headline": "Saha urges police to adopt AI-based technology' + chr(92) + 'u0027s use"}</script>'
        self.assertEqual(full_headline(page, "Saha urges police to adopt AI-based technol"),
                         "Saha urges police to adopt AI-based technology")

    def test_page_without_the_headline(self):
        self.assertEqual(full_headline("<h1>Something else</h1>", CUT), "")


if __name__ == "__main__":
    unittest.main()
