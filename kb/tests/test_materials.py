"""materials.py: what is read from a web page and from a PDF, and where each passage comes from."""

from pathlib import Path
from unittest import TestCase

from kb import materials

FIXTURES = Path(__file__).parent / "fixtures"


class ReadHtml(TestCase):
    def setUp(self):
        self.document = materials.read(FIXTURES / "page.html")

    def test_title_and_url(self):
        self.assertEqual(self.document.title, "Parking — Example city")
        self.assertEqual(self.document.url, "https://example.org/parking")

    def test_location_is_the_heading_path(self):
        self.assertEqual([p.location for p in self.document.passages], ["Parking", "Parking › Rate"])

    def test_tables_and_image_text_are_kept(self):
        self.assertIn("2025 | 2,30", self.document.text)
        self.assertIn("[figure: Rates per year]", self.document.text)

    def test_menus_scripts_and_footers_are_skipped(self):
        self.assertNotIn("Menu", self.document.text)
        self.assertNotIn("not this", self.document.text)
        self.assertNotIn("Footer", self.document.text)


class ReadPdf(TestCase):
    def test_two_columns_written_column_by_column_read_in_order(self):
        text = materials.read(FIXTURES / "two_columns.pdf").text
        self.assertLess(text.index("Left column, sentence three."), text.index("Right column, sentence one."))

    def test_location_is_the_page(self):
        self.assertEqual(materials.read(FIXTURES / "two_columns.pdf").passages[0].location, "p. 1")


class Chunk(TestCase):
    def test_blocks_are_joined_up_to_the_size(self):
        self.assertEqual(materials.chunk(["aaaa", "bbbb", "cccc"], size=9), ["aaaa\nbbbb", "cccc"])

    def test_a_long_block_is_never_split(self):
        self.assertEqual(materials.chunk(["x" * 20], size=5), ["x" * 20])
