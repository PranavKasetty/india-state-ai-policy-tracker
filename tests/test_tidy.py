"""Cleaning publishers' summaries and thumbnails (pipeline/tidy.py).

Run:  python -m unittest tests.test_tidy
"""
import unittest

from pipeline.tidy import clean_summary, first_sentence, stock_images, strip_dateline


class Sentences(unittest.TestCase):
    def test_does_not_stop_at_titles_or_initials(self):
        text = "Odisha Governor Dr. Hari Babu inaugurated a lab. More follows."
        self.assertEqual(first_sentence(text), "Odisha Governor Dr. Hari Babu inaugurated a lab.")
        self.assertEqual(first_sentence("Telangana DGP C.V. Anand urged AI policing. Next."),
                         "Telangana DGP C.V. Anand urged AI policing.")

    def test_roman_numeral_ends_a_sentence(self):
        self.assertEqual(first_sentence("Land for Phase I. Work starts soon."), "Land for Phase I.")


class Datelines(unittest.TestCase):
    def test_place_and_date_are_dropped(self):
        for line in ("Patna: The state will", "Mumbai, Oct 9: The state will",
                     "Chennai, 24th of October, 2026: The state will", "Daijiworld Media Network - Mumbai: The state will"):
            self.assertEqual(strip_dateline(line), "The state will", line)

    def test_a_sentence_with_a_colon_is_kept(self):
        for line in ("Bengaluru AI cameras: the BMC has", "“The tool is not the starting point”: he said"):
            self.assertEqual(strip_dateline(line), line)


class Summaries(unittest.TestCase):
    def test_cut_at_an_abbreviation(self):
        self.assertEqual(clean_summary("Haryana Chief Minister, Sh."), "")

    def test_site_description(self):
        self.assertEqual(clean_summary("Get latest Mumbai news headlines, local news headlines for today."), "")

    def test_good_summary_loses_only_its_dateline(self):
        self.assertEqual(clean_summary("Patna: Bihar plans an AI call centre."), "Bihar plans an AI call centre.")


class StockImages(unittest.TestCase):
    def test_logo_by_file_name_and_repeated_image(self):
        recs = [{"source_name": "Mid-Day", "image_url": "https://static.mid-day.com/assets/images/logo.svg"},
                *[{"source_name": "ThePrint", "image_url": "https://x/default_new.jpg?w=1"}] * 1,
                *[{"source_name": "TOI", "image_url": "https://static.toiimg.com/photo/47529300.jpg"}] * 3,
                {"source_name": "HT", "image_url": "https://www.hindustantimes.com/ht-img/2026/1600x900/logo/Bihar_AI_123.jpg"},
                {"source_name": "TOI", "image_url": "https://static.toiimg.com/photo/1.jpg"}]
        self.assertEqual(stock_images(recs), {"https://static.mid-day.com/assets/images/logo.svg", "https://x/default_new.jpg?w=1",
                                              "https://static.toiimg.com/photo/47529300.jpg"})


if __name__ == "__main__":
    unittest.main()
