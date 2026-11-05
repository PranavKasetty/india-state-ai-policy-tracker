"""Static state pages and feeds (pipeline/pages.py).

Run:  python -m unittest tests.test_pages
"""
import unittest
import xml.etree.ElementTree as ET

from pipeline import pages

REC = {"record_id": "R1a2b3c4d", "state": "Tamil Nadu", "date": "2026-10-02", "title": "TN launches <AI> chatbot",
       "summary": "It answers in Tamil.", "summary_source": "publisher standfirst", "source_name": "The Hindu",
       "source_url": "https://example.com/a?b=1&c=2", "also_reported_by": ["Dinamalar"], "n_sources": 2,
       "tags": ["Deployment"], "primary_category": "Deployment", "sector": "Health", "stage": "underway"}


class Pages(unittest.TestCase):
    def test_slug_matches_the_dashboard_rule(self):
        self.assertEqual(pages.slug("Tamil Nadu"), "tamil-nadu")
        self.assertEqual(pages.slug("Jammu & Kashmir"), "jammu-kashmir")

    def test_brief_citations_link_to_known_records_only(self):
        out = pages._brief_html("Kerala did X [R1a2b3c4d, R99999999]. Then Y [R99999999].", {"R1a2b3c4d"})
        self.assertIn('href="#R1a2b3c4d"', out)
        self.assertNotIn("R99999999", out)
        self.assertEqual(pages._brief_html("Kerala set up K-AIM [Ref58a154, 9641614e].", set()), "Kerala set up K-AIM.")

    def test_state_page_escapes_and_cites(self):
        profile = {"ai_policy": {"status": "done", "text": "TN AI policy 2026", "cites": ["R1a2b3c4d"]}}
        html = pages.state_page("Tamil Nadu", [REC], profile, None, "4 November 2026", "November 2025")
        self.assertIn("TN launches &lt;AI&gt; chatbot", html)
        self.assertIn('<link rel="canonical" href="https://pranavkasetty.github.io/india-state-ai-policy-tracker/state/tamil-nadu/">', html)
        self.assertIn("Adopted", html)
        self.assertIn('id="R1a2b3c4d"', html)
        self.assertIn("1 of them approved, signed, launched or in use", html)

    def test_entries_have_a_thumbnail_over_the_state_tile(self):
        with_image = pages._record({**REC, "image_url": "https://example.com/a.jpg?w=1&h=2"})
        self.assertIn('<span class="thumb-code">TN</span><img src="https://example.com/a.jpg?w=1&amp;h=2"', with_image)
        self.assertIn('onerror="this.remove()"', with_image)
        self.assertNotIn("<img", pages._record({**REC, "image_url": ""}))

    def test_feed_is_valid_rss(self):
        root = ET.fromstring(pages._rss("T", pages.SITE, "D", [REC], pages.SITE + "feed.xml"))
        item = root.find("channel/item")
        self.assertEqual(item.findtext("title"), "Tamil Nadu: TN launches <AI> chatbot")
        self.assertEqual(item.findtext("link"), "https://example.com/a?b=1&c=2")
        self.assertTrue(item.findtext("guid").endswith("#item=R1a2b3c4d"))


if __name__ == "__main__":
    unittest.main()
