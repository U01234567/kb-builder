"""index.py: reading materials once, and searching within a topic's files by meaning and by words."""

import tempfile
from pathlib import Path
from unittest import TestCase

from kb import index
from kb.tests.helpers import fake_embed, make_project


class Search(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = make_project(Path(self.tmp.name), {"Parking": ["What is the rate?"]},
                                 {"parking/page.html": "page.html", "other/two.pdf": "two_columns.pdf"})
        self.files = index.material_files(self.proj.materials)
        self.db = index.connect(self.proj.index_dir)
        self.read = index.refresh(self.db, self.proj.materials, self.files, fake_embed, self.proj.index_dir / "text")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_every_file_is_read_once(self):
        self.assertEqual(sorted(self.read), ["other/two.pdf", "parking/page.html"])
        self.assertEqual(index.refresh(self.db, self.proj.materials, self.files, fake_embed, self.proj.index_dir / "text"), [])

    def test_a_readable_text_version_is_written(self):
        self.assertIn("2,50 per hour", (self.proj.index_dir / "text" / "parking" / "page.html.txt").read_text(encoding="utf-8"))

    def test_search_stays_inside_the_scope(self):
        scope = {self.files["parking/page.html"]}
        found = index.search(self.db, "rate 2,50", scope, fake_embed, 5)
        self.assertEqual({c.fingerprint for c in found}, scope)

    def test_words_find_numbers(self):
        found = index.search(self.db, "2,30", set(self.files.values()), fake_embed, 2)
        self.assertIn("2,30", "".join(c.text for c in found))


class Helpers(TestCase):
    def test_fuse_prefers_items_high_in_both_lists(self):
        self.assertEqual(index.fuse([[1, 2, 3], [2, 1, 4]])[:2], [1, 2])

    def test_word_query_keeps_numbers_and_longer_words(self):
        self.assertEqual(index.word_query("Is 87 the rate?"), '"87" OR "the" OR "rate"')

    def test_folder(self):
        self.assertEqual(index.folder("parking/sub/page.html"), "parking")
