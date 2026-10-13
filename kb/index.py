"""The search index: every material read once, searchable by meaning and by words, filtered by folder.

Files are known by a fingerprint of their content, so renaming or moving a file never re-reads it.
"""

import hashlib
import math
import re
import shutil
import sqlite3
from array import array
from dataclasses import dataclass
from pathlib import Path

from kb import materials

SCHEMA = """
create table if not exists sources (fingerprint text primary key, title text, url text, chars integer);
create table if not exists passages (id integer primary key, fingerprint text, location text, text text, embedding blob);
create virtual table if not exists passage_words using fts5(text);
"""


@dataclass(frozen=True)
class Candidate:
    """A passage found for a question: which file (by fingerprint), where in it, and its text."""

    fingerprint: str
    location: str
    text: str


def fingerprint(path: Path) -> str:
    """A short hash of the file's content: the same content gives the same fingerprint, whatever its name."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def material_files(root: Path) -> dict[str, str]:
    """Every readable file under materials/, as relative path -> fingerprint."""
    return {path.relative_to(root).as_posix(): fingerprint(path)
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix.lower() in materials.SUPPORTED}


def by_content(files: dict[str, str]) -> dict[str, list[str]]:
    """fingerprint -> the paths that have that content (more than one path: identical files)."""
    paths: dict[str, list[str]] = {}
    for path, fp in files.items():
        paths.setdefault(fp, []).append(path)
    return paths


def folder(path: str) -> str:
    """The top-level folder of a path relative to materials/ ('' for a file directly in it)."""
    return path.split("/")[0] if "/" in path else ""


def connect(index_dir: Path) -> sqlite3.Connection:
    """The index database in `index_dir`, created when it does not exist yet."""
    index_dir.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(index_dir / "index.sqlite3")
    db.executescript(SCHEMA)
    return db


def refresh(db: sqlite3.Connection, root: Path, files: dict[str, str], embed, text_dir: Path) -> list[str]:
    """Read files with new content, forget content that is gone, rewrite the readable text versions.

    `embed` turns a list of texts into a list of vectors. Returns the paths that were read now.
    """
    known = {row[0] for row in db.execute("select fingerprint from sources")}
    for gone in known - set(files.values()):
        db.execute("delete from passage_words where rowid in (select id from passages where fingerprint = ?)", (gone,))
        db.execute("delete from passages where fingerprint = ?", (gone,))
        db.execute("delete from sources where fingerprint = ?", (gone,))
    read_now = []
    for path, fp in files.items():
        if fp in known:
            continue
        known.add(fp)  # an identical file under another path is read only once
        document = materials.read(root / path)
        vectors = embed([p.text for p in document.passages]) if document.passages else []
        db.execute("insert into sources values (?, ?, ?, ?)", (fp, document.title, document.url, len(document.text)))
        for passage, vector in zip(document.passages, vectors):
            row = db.execute("insert into passages (fingerprint, location, text, embedding) values (?, ?, ?, ?)",
                             (fp, passage.location, passage.text, unit(vector).tobytes()))
            db.execute("insert into passage_words (rowid, text) values (?, ?)", (row.lastrowid, passage.text))
        db.commit()  # per file, so an interrupted run keeps what it already read
        read_now.append(path)
    write_texts(db, files, text_dir)
    return read_now


def write_texts(db: sqlite3.Connection, files: dict[str, str], text_dir: Path) -> None:
    """One readable .txt per material: what the reader made of it, to check by eye."""
    shutil.rmtree(text_dir, ignore_errors=True)
    for path, fp in files.items():
        title, url = db.execute("select title, url from sources where fingerprint = ?", (fp,)).fetchone()
        parts = [f"# {title}", url or "(no url found)", ""]
        parts += [f"[{location}]\n{text}\n" for location, text in
                  db.execute("select location, text from passages where fingerprint = ? order by id", (fp,))]
        target = text_dir / f"{path}.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(parts), encoding="utf-8")


def sources(db: sqlite3.Connection) -> dict[str, tuple[str, str, int]]:
    """fingerprint -> (title, url, number of characters read), for every file in the index."""
    return {row[0]: row[1:] for row in db.execute("select fingerprint, title, url, chars from sources")}


def full_text(db: sqlite3.Connection, fp: str) -> str:
    """All text read from the file with fingerprint `fp`, to check quotes against."""
    return "\n".join(row[0] for row in db.execute("select text from passages where fingerprint = ?", (fp,)))


def search(db: sqlite3.Connection, question: str, scope: set[str], embed, k: int) -> list[Candidate]:
    """The k best passages for `question` within `scope` (fingerprints).

    Two rankings, merged: by meaning (embeddings) and by words (full-text search, which also finds
    numbers such as 2,50 that embeddings tend to miss).
    """
    rows = {row[0]: row for row in db.execute("select id, fingerprint, location, text, embedding from passages")
            if row[1] in scope}
    query = unit(embed([question])[0])
    by_meaning = sorted(rows, key=lambda i: -similarity(query, rows[i][4]))[:k]
    words = word_query(question)
    hits = db.execute("select rowid from passage_words where passage_words match ? order by rank limit ?",
                      (words, k * 10)) if words else []
    by_words = [row[0] for row in hits if row[0] in rows][:k]
    return [Candidate(*rows[i][1:4]) for i in fuse([by_meaning, by_words])[:k]]


def word_query(question: str) -> str:
    """A full-text query matching any word of three or more characters, and any number."""
    words = dict.fromkeys(w.lower() for w in re.findall(r"\w+", question) if len(w) > 2 or w.isdigit())
    return " OR ".join(f'"{w}"' for w in words)


def fuse(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal rank fusion: items ranked high in any of the lists come first."""
    score: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            score[item] = score.get(item, 0) + 1 / (k + rank + 1)
    return sorted(score, key=lambda item: -score[item])


def unit(vector: list[float]) -> array:
    """The vector scaled to length 1, so comparing two of them is a plain dot product."""
    length = math.sqrt(sum(x * x for x in vector)) or 1.0
    return array("f", (x / length for x in vector))


def similarity(query: array, blob: bytes) -> float:
    """Cosine similarity between a unit query vector and a stored unit vector."""
    stored = array("f")
    stored.frombytes(blob)
    return sum(x * y for x, y in zip(query, stored))
