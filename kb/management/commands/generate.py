"""python manage.py generate: on a GPU server, answer the questions in kb.xlsx from the materials.

The thin shell around the modules: preflight, your yes/no, what to run, then per question
search, judge, answer, save. Saving after every question means an interrupted run loses nothing.
"""

import platform
import shutil
import subprocess
import sys
from datetime import datetime
from functools import partial

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from kb import answer, index, ollama, preflight, project, workbook
from kb.management.commands.preflight import ask, check

FREE_MB = 1024  # a GPU using more memory than this is taken to be busy


class Command(BaseCommand):
    """python manage.py generate [--mode missing|all] [--topics ...] [--yes]"""

    help = "Generate answers for kb.xlsx (needs the GPUs)."

    def add_arguments(self, parser):
        """Everything generate asks in the terminal can also be given here, for runs with nohup."""
        parser.add_argument("--mode", choices=["missing", "all"],
                            help="missing: only questions without an answer; all: run chosen topics again")
        parser.add_argument("--topics", default="", help="with --mode all: topic names separated by commas (default: all)")
        parser.add_argument("--yes", action="store_true", help="the Topics sheet is checked; do not ask (for nohup)")

    def handle(self, *args, mode, topics, yes, **options):
        """Preflight, confirm, choose, back up, then answer the chosen questions one by one."""
        proj = project.load(settings.PROJECT_DIR)
        state = check(self, proj)
        interactive = sys.stdin.isatty()
        if not yes and not interactive:
            raise CommandError("Without a terminal, add --yes (and --mode) to confirm the Topics sheet.")
        if not yes and ask("Check the Topics sheet in kb.xlsx. Is this correct?\n  [y] yes, continue\n"
                           "  [n] no / I haven't checked yet") == "n":
            raise CommandError("Stopped. Check the Topics sheet, then start again.")
        wb = state.wb
        mode = mode or choose_mode(wb, proj, interactive)
        chosen = choose_topics(wb, topics, interactive) if mode == "all" else workbook.topic_sheets(wb)
        busy = busy_gpus(proj.gpus)
        if busy:
            raise CommandError(f"GPU {', '.join(busy)} is in use (see nvidia-smi). Wait, or change gpus in project.toml.")
        if mode == "all":
            proj.backups.mkdir(exist_ok=True)
            backup = proj.backups / f"kb-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
            shutil.copy2(proj.kb_path, backup)
            self.stdout.write(f"Backup: {backup}")
        workbook.prepare(wb, proj, {index.folder(p) for p in state.files} - {""})
        stamp = workbook.save(wb, proj.kb_path, state.stamp, proj)
        started = f"{datetime.now():%Y-%m-%d %H:%M}"
        judge_prompt, answer_prompt = proj.prompt("judge"), proj.prompt("answer")
        with ollama.running(proj.gpus, proj.context) as client:
            for model in (proj.llm, proj.embeddings):
                self.stdout.write(f"Model {model}: downloading if needed…")
                for progress in client.pull(model):
                    self.stdout.write(f"  {progress}")
            embed = partial(client.embed, proj.embeddings)
            chat = partial(client.chat, proj.llm)
            db = index.connect(proj.index_dir)
            for path in index.refresh(db, proj.materials, state.files, embed, proj.index_dir / "text"):
                self.stdout.write(f"Read {path}")
            documents = index.sources(db)
            ids = workbook.sync_sources(wb, state.files, documents, saved_dates(proj, state.files))
            titles = {fp: info[0] for fp, info in documents.items()}
            reads = workbook.topics(wb)
            rows = workbook.questions(wb, proj)
            todo = preflight.open_questions(rows) if mode == "missing" else [q for q in rows if q["_sheet"] in chosen]
            for number, q in enumerate(todo, start=1):
                scope = preflight.scope(reads[q["_sheet"]], state.files)
                candidates = index.search(db, q["question"], scope, embed, proj.candidates)
                kept = answer.judge(chat, judge_prompt, q["question"], candidates, titles)
                result = answer.write(chat, answer_prompt, q["question"], kept, titles, proj.question_variants, proj.not_found)
                workbook.write_answer(wb, proj, q, result, ids, started, preflight.scope_print(scope))
                stamp = workbook.save(wb, proj.kb_path, stamp, proj)
                self.stdout.write(f"[{number}/{len(todo)}] {q['id']} ({q['_sheet']}): {len(kept)} of {len(candidates)} passages kept")
            workbook.verify_evidence(wb, checker(db, ids, rows, reads, state.files))
        workbook.add_row(wb[workbook.RUNS], {
            "Started": started, "Finished": f"{datetime.now():%Y-%m-%d %H:%M}", "Machine": platform.node(),
            "Mode": mode, "Topics": ", ".join(chosen), "Model": proj.llm, "Embeddings": proj.embeddings,
            "Prompts": workbook.fingerprint(judge_prompt + answer_prompt), "Questions": len(todo)})
        workbook.save(wb, proj.kb_path, stamp, proj)
        self.stdout.write(f"Done: {len(todo)} questions. Next: copy kb.xlsx to the computer you review on.")


def choose_mode(wb, proj, interactive: bool) -> str:
    """Ask what this run does: 'missing' (open questions only) or 'all' (chosen topics again)."""
    if not interactive:
        raise CommandError("Without a terminal, add --mode missing or --mode all.")
    open_count = len(preflight.open_questions(workbook.questions(wb, proj)))
    reply = ask("What should this run do?\n"
                f"  [1] Only questions without a generated answer ({open_count})\n"
                "  [2] Full run again for chosen topics (backup first; answers and reviews replaced)", ("1", "2"))
    return "missing" if reply == "1" else "all"


def choose_topics(wb, given: str, interactive: bool) -> list[str]:
    """The topics for a full run: from --topics, else asked by number (Enter, or no terminal: all)."""
    sheets = workbook.topic_sheets(wb)
    if given:
        names = [name.strip() for name in given.split(",")]
        unknown = [name for name in names if name not in sheets]
        if unknown:
            raise CommandError(f"Unknown topic(s): {', '.join(unknown)}. Topics: {', '.join(sheets)}.")
        return names
    if not interactive:
        return sheets
    listing = "\n".join(f"  [{n}] {name}" for n, name in enumerate(sheets, start=1))
    reply = input(f"Which topics? Numbers separated by commas; Enter = all.\n{listing}\n> ").strip()
    if not reply:
        return sheets
    return [sheets[int(n) - 1] for n in reply.split(",") if n.strip().isdigit() and 0 < int(n) <= len(sheets)]


def busy_gpus(gpus: str) -> list[str]:
    """The GPUs from project.toml that already use memory, according to nvidia-smi."""
    try:
        output = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        raise CommandError("nvidia-smi was not found: generate needs a computer with NVIDIA GPUs.") from None
    used = {gpu.strip(): int(mb) for gpu, mb in (line.split(",") for line in output.strip().splitlines())}
    return [gpu.strip() for gpu in gpus.split(",") if used.get(gpu.strip(), 0) > FREE_MB]


def saved_dates(proj, files: dict) -> dict:
    """path -> the date the file was last saved, for the 'Saved on' column of new sources."""
    return {path: f"{datetime.fromtimestamp((proj.materials / path).stat().st_mtime):%Y-%m-%d}" for path in files}


def checker(db, ids: dict, rows: list, reads: dict, files: dict):
    """A check(question, source, quote) for workbook.verify_evidence, against the files on disk now."""
    fingerprint_of = {source_id: fp for fp, source_id in ids.items()}
    scopes = {sheet: preflight.scope(topic_reads, files) for sheet, topic_reads in reads.items()}
    sheet_of = {q["id"]: q["_sheet"] for q in rows}

    def check_quote(question_id: str, source_id: str, quote: str) -> str:
        """'✓', or '✗' with the reason: the source is gone, outside the topic, or does not contain the quote."""
        fp = fingerprint_of.get(source_id)
        if fp is None:
            return "✗ source missing"
        if fp not in scopes.get(sheet_of.get(question_id), {fp}):
            return "✗ outside topic"
        return "✓" if answer.verify(quote, index.full_text(db, fp)) else "✗ not in source"

    return check_quote
