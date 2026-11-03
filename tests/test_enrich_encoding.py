"""Decoding publisher pages (pipeline/enrich.py): UTF-8 pages served without a
charset must not turn "’" into "â\x80\x99".

Run:  python -m unittest tests.test_enrich_encoding
"""
import unittest

import requests
from requests.utils import get_encoding_from_headers

from pipeline.enrich import page_text, repair_mojibake

PAGE = '<html><head>{meta}<meta property="og:description" content="Lucknow’s policing…"></head></html>'


def response(body: bytes, content_type: str) -> requests.Response:
    """A Response as requests builds it: encoding guessed from the header alone."""
    r = requests.Response()
    r._content = body
    r.headers["content-type"] = content_type
    r.encoding = get_encoding_from_headers(r.headers)
    return r


class PageText(unittest.TestCase):
    def test_utf8_without_charset_header(self):
        r = response(PAGE.format(meta="").encode("utf-8"), "text/html")
        self.assertEqual(r.encoding, "ISO-8859-1")  # the requests default that caused the bug
        self.assertIn("Lucknow’s policing…", page_text(r))

    def test_meta_charset_is_used(self):
        body = PAGE.format(meta='<meta charset="windows-1252">').replace("…", "").encode("cp1252")
        self.assertIn("Lucknow’s policing", page_text(response(body, "text/html")))

    def test_header_charset_wins(self):
        r = response(PAGE.format(meta="").encode("utf-8"), "text/html; charset=utf-8")
        self.assertIn("Lucknow’s", page_text(r))

    def test_unknown_charset_does_not_crash(self):
        body = PAGE.format(meta='<meta charset="no-such-charset">').encode("utf-8")
        self.assertIn("Lucknow", page_text(response(body, "text/html")))


class RepairMojibake(unittest.TestCase):
    def test_repairs_runs_next_to_real_unicode(self):
        garbled = "The stateâ\u0080\u0099s system…"  # as stored: mojibake plus a real "…"
        self.assertEqual(repair_mojibake(garbled), "The state’s system…")

    def test_leaves_clean_text_alone(self):
        for text in ["Café ₹1,725 crore", "naïve façade", "Tamil Nadu’s plan"]:
            self.assertEqual(repair_mojibake(text), text)


if __name__ == "__main__":
    unittest.main()
