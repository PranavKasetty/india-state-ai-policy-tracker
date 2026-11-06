"""Resolving Google News links when Google's reply is not the usual one (pipeline/enrich.py).

Run:  python -m unittest tests.test_enrich_resolve
"""
import unittest
from unittest import mock

from pipeline import enrich

PAGE = mock.Mock(text='data-n-a-id="a" data-n-a-ts="1" data-n-a-sg="s"')


def resolve(reply: str) -> str:
    with mock.patch.object(enrich.SESSION, "get", return_value=PAGE), \
         mock.patch.object(enrich.SESSION, "post", return_value=mock.Mock(text=reply)):
        return enrich.resolve_url("https://news.google.com/rss/articles/x")


class Resolve(unittest.TestCase):
    def test_usual_reply(self):
        self.assertEqual(resolve(')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://example.com/a\\",1]"]]'),
                         "https://example.com/a")

    def test_throttling_page_or_odd_reply_is_a_refusal_not_a_crash(self):
        for reply in ("<html>Too many requests</html>", ")]}'\n\n[]", ')]}\'\n\n[["wrb.fr","Fbv4je","[null,5]"]]'):
            self.assertEqual(resolve(reply), "", reply)


if __name__ == "__main__":
    unittest.main()
