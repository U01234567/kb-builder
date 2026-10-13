"""python manage.py preflight: check kb.xlsx and materials/ without running anything.

generate and review run the same check first, through check() below.
"""

import sqlite3
import sys
from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from kb import index, materials, preflight, project, workbook


@dataclass(frozen=True)
class State:
    """What a passed preflight hands on: the open workbook, its stamp, and the files in materials/."""

    wb: object
    stamp: str
    files: dict | None


def check(command: BaseCommand, proj, with_materials: bool = True) -> State:
    """Run the preflight, print it, offer its fixes, and stop (CommandError) on anything that blocks a run.

    Accepted fixes are saved, and the preflight runs again. Without `with_materials`, only the
    workbook is checked (a laptop that only reviews has no materials/).
    """
    if not proj.kb_path.is_file():
        raise CommandError(f"{proj.kb_path} is missing.")
    wb, stamp = workbook.open_kb(proj.kb_path)
    files = index.material_files(proj.materials) if with_materials else None
    unsupported = [p.relative_to(proj.materials).as_posix() for p in sorted(proj.materials.rglob("*"))
                   if p.is_file() and not p.name.startswith(".") and p.suffix.lower() not in materials.SUPPORTED
                   ] if with_materials else []
    chars = {}
    if (proj.index_dir / "index.sqlite3").is_file():
        with sqlite3.connect(proj.index_dir / "index.sqlite3") as db:
            chars = {fp: info[2] for fp, info in index.sources(db).items()}
    findings, lines = preflight.run(wb, proj, files, unsupported, chars)
    command.stdout.write(f"Preflight (also on its own: python manage.py preflight)\n{preflight.report(findings, lines)}\n")
    accepted = [f for f in findings if f.fix and sys.stdin.isatty()
                and ask(f"{f.text}\n  [y] update the Topics sheet  [n] leave it") == "y"]
    if accepted:
        for finding in accepted:
            workbook.apply_fix(wb, finding.fix)
        workbook.prepare(wb, proj, {index.folder(p) for p in files or {}} - {""})
        workbook.save(wb, proj.kb_path, stamp, proj)
        return check(command, proj, with_materials)
    stops = [f for f in findings if f.level == "stop"]
    if stops:
        raise CommandError(f"{len(stops)} problem(s) stop a run. Fix them and run the preflight again.")
    return State(wb, stamp, files)


def ask(question: str, answers: tuple = ("y", "n")) -> str:
    """Ask in the terminal until the reply is one of `answers`."""
    while True:
        reply = input(f"{question}\n> ").strip().lower()
        if reply in answers:
            return reply


class Command(BaseCommand):
    """python manage.py preflight [--workbook-only]"""

    help = "Check kb.xlsx and materials/ before a run: x stops a run, ! is a warning."

    def add_arguments(self, parser):
        """--workbook-only skips materials/, for a laptop that only reviews."""
        parser.add_argument("--workbook-only", action="store_true", help="skip materials/ (on a laptop that only reviews)")

    def handle(self, *args, workbook_only, **options):
        """Run the preflight and end with a one-line summary when nothing stops a run."""
        proj = project.load(settings.PROJECT_DIR)
        state = check(self, proj, with_materials=not workbook_only)
        rows = workbook.questions(state.wb, proj)
        evidence = len(workbook.records(state.wb[workbook.EVIDENCE])) if workbook.EVIDENCE in state.wb.sheetnames else 0
        self.stdout.write(f"\nNothing stops a run. Topics: {len(workbook.topic_sheets(state.wb))} · questions: {len(rows)} · "
                          f"files: {len(state.files or {})} · evidence rows: {evidence}")
