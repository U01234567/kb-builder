"""Everything that can be wrong before a run, as a list: 'stop' findings block a run, 'warn' findings inform.

Pure: it reads a workbook and a list of files, and changes nothing. A finding may carry a fix
(see workbook.apply_fix) that the commands offer with a yes/no question.
"""

import difflib
from collections import Counter
from dataclasses import dataclass

from kb import workbook
from kb.index import by_content, folder

LITTLE_TEXT = 300  # characters; less than this from a whole file usually means a failed save


@dataclass(frozen=True)
class Finding:
    """One problem: 'stop' blocks a run, 'warn' only informs. `fix` is an optional workbook.apply_fix tuple."""

    level: str
    text: str
    fix: tuple | None = None


@dataclass(frozen=True)
class TopicLine:
    """One row of the topic table the preflight prints."""

    topic: str
    reads: str
    files: int
    open: int
    note: str


def scope(reads: str, files: dict[str, str]) -> set[str]:
    """Fingerprints of the files a topic reads, given its Reads cell."""
    names = workbook.read_folders(reads, {folder(p) for p in files} - {""})
    return {fp for path, fp in files.items() if folder(path) in names}


def scope_print(fingerprints: set[str]) -> str:
    """One fingerprint for a set of files: it changes when a file is added, removed or changed."""
    return workbook.fingerprint(",".join(sorted(fingerprints)))


def open_questions(rows: list[dict]) -> list[dict]:
    """Questions without an answer, or whose text changed since they were answered."""
    return [q for q in rows if not q["answer"] or q["asked"] != workbook.fingerprint(q["question"])]


def run(wb, project, files: dict[str, str] | None, unsupported: list[str], chars: dict[str, int]):
    """All findings, and one TopicLine per topic.

    `files` is materials/ as path -> fingerprint, or None to check the workbook only (on a laptop
    that only reviews). `unsupported` lists files of other types; `chars` is fingerprint -> number
    of characters read, from the index.
    """
    sheets = workbook.topic_sheets(wb)
    labels = project.topic_columns()
    if not sheets:
        return [Finding("stop", f'kb.xlsx has no topic sheets yet. Add a sheet per topic with a "{labels["question"]}" column.')], []
    rows = workbook.questions(wb, project)
    sources = workbook.records(wb[workbook.SOURCES]) if workbook.SOURCES in wb.sheetnames else []
    findings = check_columns(wb, sheets, labels)
    findings += duplicates("question number", [q["id"] for q in rows if q["id"]])
    findings += duplicates("source number", [r["ID"] for r in sources if r.get("ID")])
    findings += same_url(sources)
    findings += check_evidence(wb, rows)
    if files is None:
        return findings, []
    folders = {folder(p) for p in files} - {""}
    written = workbook.topics(wb)
    reads = {sheet: written.get(sheet, workbook.slug(sheet)) for sheet in sheets}  # a new topic: its guessed folder
    findings += check_topics(written, sheets, folders, files, sources)
    findings += check_files(files, unsupported, chars, folders, reads)
    return findings, topic_lines(rows, reads, written, files, folders)


def check_columns(wb, sheets: list[str], labels: dict) -> list[Finding]:
    """Every topic sheet has a question column; once answered, it still has every column of project.toml."""
    findings = []
    shown = [h for key, h in labels.items() if key not in ("asked", "scope")]
    for sheet in sheets:
        present = workbook.headers(wb[sheet])
        if labels["question"] not in present:
            findings.append(Finding("stop", f'Sheet "{sheet}": column "{labels["question"]}" is missing.'))
        elif labels["id"] in present:
            findings += [Finding("stop", f'Sheet "{sheet}": column "{h}" is missing (expected from project.toml).')
                         for h in shown if h not in present]
    return findings


def duplicates(what: str, values: list[str]) -> list[Finding]:
    """A stop for every number that is used more than once."""
    return [Finding("stop", f"The {what} {value} is used {count} times. Each must be unique.")
            for value, count in Counter(values).items() if count > 1]


def same_url(sources: list[dict]) -> list[Finding]:
    """A warning when two sources with different content have the same URL: which one is current?"""
    by_url: dict[str, list[dict]] = {}
    for r in sources:
        if r.get("URL") and r.get("Status") != "missing":
            by_url.setdefault(r["URL"], []).append(r)
    return [Finding("warn", "Same URL, different content:\n" + "\n".join(
                f"    {r['Files']}  (saved {r.get('Saved on') or '?'})" for r in rows) + "\n  Which one is current?")
            for rows in by_url.values() if len(rows) > 1]


def check_evidence(wb, rows: list[dict]) -> list[Finding]:
    """Warnings for evidence of questions that are gone, and for quotes that failed the check."""
    if workbook.EVIDENCE not in wb.sheetnames:
        return []
    evidence = workbook.records(wb[workbook.EVIDENCE])
    ids = {q["id"] for q in rows}
    orphans = sum(1 for r in evidence if r["Question"] not in ids)
    failed = sum(1 for r in evidence if str(r.get("Verified") or "").startswith("✗") and not r.get("Removed"))
    return ([Finding("warn", f"{orphans} evidence rows belong to questions that no longer exist.")] if orphans else []) + \
           ([Finding("warn", f"{failed} quotes could not be verified. See the Verified column in Evidence.")] if failed else [])


def check_topics(written: dict, sheets: list[str], folders: set[str], files: dict, sources: list[dict]) -> list[Finding]:
    """The Topics sheet against the topic sheets and the folders, with a fix where the cause is clear.

    A Topics row without a sheet (renamed sheet?), a new topic without a folder, a topic that reads
    nothing, and a folder in Reads that does not exist (renamed folder? typo?).
    """
    findings = []
    orphans = [t for t in written if t not in sheets]
    newcomers = [s for s in sheets if s not in written]
    for topic in orphans:
        fix = ("rename_topic", topic, newcomers[0]) if len(orphans) == 1 and len(newcomers) == 1 else None
        hint = f' Renamed to "{newcomers[0]}"?' if fix else ""
        findings.append(Finding("stop", f'Topics: "{topic}" has no sheet any more.{hint}', fix))
    for sheet in newcomers:
        if workbook.slug(sheet) not in folders:
            findings.append(Finding("stop", f'New topic "{sheet}": materials/{workbook.slug(sheet)}/ has no sources '
                                            f'(or does not exist). Add sources there, or write its folders in the '
                                            f'Reads column of the Topics sheet.'))
    for topic, reads in written.items():
        if not reads:
            findings.append(Finding("stop", f'Topics: "{topic}" reads nothing. Write folders, or * for all.'))
        for name in workbook.read_folders(reads, folders) - folders:
            findings.append(missing_folder(topic, reads, name, folders, files, sources))
    return findings


def missing_folder(topic: str, reads: str, name: str, folders: set[str], files: dict, sources: list[dict]) -> Finding:
    """A stop for a folder in Reads that does not exist, with a fix when there is a likely replacement.

    Likely: a folder holding exactly the files the missing one held (per the Sources sheet), else a
    folder with a similar name.
    """
    held = {r["Fingerprint"] for r in sources for path in str(r.get("Files") or "").splitlines() if folder(path) == name}
    renamed = [f for f in sorted(folders) if held and {fp for p, fp in files.items() if folder(p) == f} == held]
    close = renamed or difflib.get_close_matches(name, sorted(folders), n=1, cutoff=0.6)
    text = f'Topics: "{topic}" reads "{name}", but that folder does not exist.'
    if not close:
        return Finding("stop", text)
    how = "has exactly the same files. Renamed?" if renamed else "exists. Did you mean that?"
    new_reads = ", ".join(close[0] if part.strip() == name else part.strip() for part in reads.split(","))
    return Finding("stop", f"{text} materials/{close[0]}/ {how}", ("set_reads", topic, new_reads))


def check_files(files: dict, unsupported: list[str], chars: dict, folders: set[str], reads: dict) -> list[Finding]:
    """Warnings about the files: unread folders, loose or unsupported files, identical files, near-empty files."""
    specific = set().union(*(workbook.read_folders(r, folders) for r in reads.values() if r.strip() != "*"))
    findings = [Finding("warn", f'materials/{name}/ is only read by "*" topics, or by none. Missing in a topic?')
                for name in sorted(folders - specific)]
    findings += [Finding("warn", f"{path} is not in a folder, so no topic reads it.") for path in files if not folder(path)]
    findings += [Finding("warn", f"{path} is ignored: only .pdf, .html and .htm are read.") for path in unsupported]
    paths_of = by_content(files)
    findings += [Finding("warn", "Identical files (same content):\n" + "\n".join(f"    {p}" for p in paths)
                         + "\n  On purpose? Then ignore this. Not on purpose? Delete one.")
                 for paths in paths_of.values() if len(paths) > 1]
    findings += [Finding("warn", f"{paths_of[fp][0]} gives almost no text ({n} characters). Saved before the page had loaded?")
                 for fp, n in chars.items() if fp in paths_of and n < LITTLE_TEXT]
    return findings


def topic_lines(rows: list[dict], reads: dict, written: dict, files: dict, folders: set[str]) -> list[TopicLine]:
    """Per topic: what it reads, how many files that is, open questions, and what changed since the answers."""
    lines = []
    for sheet, topic_reads in reads.items():
        fingerprints = scope(topic_reads, files)
        answered = [q for q in rows if q["_sheet"] == sheet and q["answer"]]
        stale = sum(1 for q in answered if q["scope"] != scope_print(fingerprints))
        changed = sum(1 for q in answered if q["asked"] != workbook.fingerprint(q["question"]))
        notes = [] if sheet in written else ["new topic: folder guessed"]
        notes += [f"files changed since {stale} answers"] if stale else []
        notes += [f"{changed} questions changed since answered"] if changed else []
        shown = f"* (all {len(folders)} folders)" if topic_reads.strip() == "*" else topic_reads
        open_count = len(open_questions([q for q in rows if q["_sheet"] == sheet]))
        lines.append(TopicLine(sheet, shown, len(fingerprints), open_count, "; ".join(notes)))
    return lines


def report(findings: list[Finding], lines: list[TopicLine]) -> str:
    """The preflight as text for the terminal: the topic table, then what stops a run, then warnings."""
    out = []
    if lines:
        width = max(len(line.reads) for line in lines)
        out.append(f"  {'Topic':<22}{'Reads':<{width + 2}}{'Files':>5}{'Open':>6}  Note")
        out += [f"  {t.topic:<22}{t.reads:<{width + 2}}{t.files:>5}{t.open:>6}  {t.note}" for t in lines]
    for level, title, mark in (("stop", "Stops a run", "x"), ("warn", "Warnings", "!")):
        chosen = [f for f in findings if f.level == level]
        if chosen:
            out += ["", title] + [f"  {mark} {f.text}" for f in chosen]
    return "\n".join(out)
