"""preflight.py: what stops a run, what only warns, and which fixes are offered."""

import tempfile
from pathlib import Path
from unittest import TestCase

from kb import index, preflight, workbook
from kb.tests.helpers import make_project


class Preflight(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = make_project(Path(self.tmp.name), {"Parking": ["Rate?"], "General": ["What?"]},
                                 {"parking/page.html": "page.html", "transport/copy.html": "page.html"})
        self.wb, _ = workbook.open_kb(self.proj.kb_path)
        self.files = index.material_files(self.proj.materials)

    def tearDown(self):
        self.tmp.cleanup()

    def texts(self, level):
        """The texts of the findings at this level ('stop' or 'warn')."""
        findings, _ = preflight.run(self.wb, self.proj, self.files, [], {})
        return [f.text for f in findings if f.level == level]

    def set_reads(self, reads):
        """Prepare the workbook, then set what the topic 'General' reads."""
        workbook.prepare(self.wb, self.proj, {"parking", "transport"})
        workbook.apply_fix(self.wb, ("set_reads", "General", reads))

    def test_a_new_topic_without_a_matching_folder_stops(self):
        self.assertIn('New topic "General": materials/general/ has no sources (or does not exist). '
                      'Add sources there, or write its folders in the Reads column of the Topics sheet.', self.texts("stop"))

    def test_identical_files_are_a_warning(self):
        self.assertTrue(any(t.startswith("Identical files") for t in self.texts("warn")))

    def test_star_reads_everything(self):
        self.set_reads("*")
        self.assertEqual(self.texts("stop"), [])

    def test_a_typo_in_reads_stops_with_a_suggestion(self):
        self.set_reads("transprot")
        findings, _ = preflight.run(self.wb, self.proj, self.files, [], {})
        self.assertEqual([f.fix for f in findings if f.fix], [("set_reads", "General", "transport")])

    def test_a_renamed_topic_sheet_is_offered_as_a_rename(self):
        self.set_reads("*")
        self.wb["General"].title = "General questions"
        findings, _ = preflight.run(self.wb, self.proj, self.files, [], {})
        self.assertEqual([f.fix for f in findings if f.fix], [("rename_topic", "General", "General questions")])

    def test_duplicate_question_numbers_stop(self):
        self.set_reads("*")
        workbook.put(self.wb["General"], 2, "ID", "Q001")
        self.assertIn("The question number Q001 is used 2 times. Each must be unique.", self.texts("stop"))

    def test_workbook_only_skips_the_materials(self):
        findings, lines = preflight.run(self.wb, self.proj, None, [], {})
        self.assertEqual((findings, lines), ([], []))
