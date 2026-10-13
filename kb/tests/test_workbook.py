"""workbook.py: numbering, guessing folders, refusing to overwrite, and keeping sources stable."""

import tempfile
from pathlib import Path
from unittest import TestCase

from kb import workbook
from kb.tests.helpers import make_project


class Helpers(TestCase):
    def test_slug(self):
        self.assertEqual(workbook.slug("Opening Hours"), "opening-hours")
        self.assertEqual(workbook.slug("Café & Façade"), "cafe-facade")

    def test_reads_star_means_every_folder(self):
        self.assertEqual(workbook.read_folders("*", {"a", "b"}), {"a", "b"})

    def test_reads_lists_folders(self):
        self.assertEqual(workbook.read_folders("a, c ,", {"a", "b"}), {"a", "c"})

    def test_next_id(self):
        self.assertEqual(workbook.next_id("Q", ["Q001", "Q009", None, "x"]), "Q010")


class Workbook(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = make_project(Path(self.tmp.name), {"Parking": ["Rate?", "Who pays?"], "General": ["What?"]}, {})
        self.wb, self.stamp = workbook.open_kb(self.proj.kb_path)
        workbook.prepare(self.wb, self.proj, {"parking"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare_numbers_questions_across_sheets(self):
        self.assertEqual([q["id"] for q in workbook.questions(self.wb, self.proj)], ["Q001", "Q002", "Q003"])

    def test_prepare_guesses_folders_it_finds_and_leaves_the_rest_empty(self):
        self.assertEqual(workbook.topics(self.wb), {"Parking": "parking", "General": ""})

    def test_save_refuses_when_someone_else_saved_in_between(self):
        self.proj.kb_path.write_bytes(self.proj.kb_path.read_bytes() + b" ")
        with self.assertRaises(workbook.ChangedOnDisk):
            workbook.save(self.wb, self.proj.kb_path, self.stamp, self.proj)

    def test_save_writes_the_fixed_sheets_in_order(self):
        workbook.save(self.wb, self.proj.kb_path, self.stamp, self.proj)
        reopened, _ = workbook.open_kb(self.proj.kb_path)
        self.assertEqual(reopened.sheetnames, ["Overview", "Parking", "General", "Topics", "Evidence", "Sources", "Runs"])


class Sources(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        proj = make_project(Path(self.tmp.name), {"Parking": ["Rate?"]}, {})
        self.wb, _ = workbook.open_kb(proj.kb_path)
        workbook.prepare(self.wb, proj, set())
        documents = {"f1": ("Page", "https://example.org", 500)}
        workbook.sync_sources(self.wb, {"a/page.html": "f1"}, documents, {})

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        """The Sources sheet as records."""
        return workbook.records(self.wb[workbook.SOURCES])

    def test_a_moved_file_keeps_its_id(self):
        ids = workbook.sync_sources(self.wb, {"b/page.html": "f1"}, {}, {})
        self.assertEqual((ids, self.rows()[0]["Files"]), ({"f1": "S001"}, "b/page.html"))

    def test_new_content_at_the_same_path_keeps_id_title_and_url(self):
        ids = workbook.sync_sources(self.wb, {"a/page.html": "f2"}, {"f2": ("Other", "", 9)}, {})
        row = self.rows()[0]
        self.assertEqual((ids, row["Title"], row["URL"]), ({"f2": "S001"}, "Page", "https://example.org"))

    def test_new_files_get_new_numbers_and_identical_files_share_one(self):
        ids = workbook.sync_sources(self.wb, {"a/page.html": "f1", "b/x.pdf": "f2", "c/y.pdf": "f3", "d/x.pdf": "f2"}, {}, {})
        self.assertEqual(ids, {"f1": "S001", "f2": "S002", "f3": "S003"})

    def test_a_removed_file_is_marked_missing(self):
        workbook.sync_sources(self.wb, {}, {}, {})
        self.assertEqual(self.rows()[0]["Status"], "missing")
