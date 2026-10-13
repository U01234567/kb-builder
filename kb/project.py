"""Read /project/project.toml into one frozen Project, so the rest of the code never parses TOML."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

# The engine knows these column keys. A project may give them other headers in [columns].
DEFAULT_HEADERS = {
    "id": "ID",
    "question": "Question",
    "answer": "Answer",
    "answer_simple": "Answer (simple)",
    "question_variant": "Question variant {n}",
    "sources": "Sources",
    "status": "Status",
    "comment": "Comment",
    "final_answer": "Final answer",
    "reviewer": "Reviewer",
    "reviewed_at": "Reviewed at",
    "run": "Run",
}


@dataclass(frozen=True)
class Project:
    """One project folder: where its files are, and the settings from its project.toml."""

    root: Path
    kb_path: Path
    materials: Path
    index_dir: Path
    backups: Path
    llm: str
    embeddings: str
    gpus: str
    context: int
    candidates: int
    question_variants: int
    not_found: str
    headers: dict

    def prompt(self, name: str) -> str:
        """The text of prompts/<name>.txt, read fresh so edits count from the next question on."""
        return (self.root / "prompts" / f"{name}.txt").read_text(encoding="utf-8")

    def topic_columns(self) -> dict:
        """Column key -> header, in the order a topic sheet shows them.

        The last two, 'asked' and 'scope', are hidden columns kb-builder uses to notice that a
        question or the files of its topic changed after it was answered.
        """
        h = self.headers
        variants = {f"question_variant_{n}": h["question_variant"].format(n=n)
                    for n in range(1, self.question_variants + 1)}
        return {"id": h["id"], "question": h["question"], "answer": h["answer"],
                "answer_simple": h["answer_simple"], **variants, "sources": h["sources"],
                "status": h["status"], "comment": h["comment"], "final_answer": h["final_answer"],
                "reviewer": h["reviewer"], "reviewed_at": h["reviewed_at"], "run": h["run"],
                "asked": "asked", "scope": "scope"}


def load(root: Path) -> Project:
    """The Project in `root`, with defaults for every setting that project.toml leaves out.

    Only the two model names are required; a missing one stops with the file and key in the message.
    """
    path = root / "project.toml"
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing. Run the start script once to create /project/.")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    model, run = data.get("model", {}), data.get("run", {})
    for key in ("llm", "embeddings"):
        if key not in model:
            raise ValueError(f"{path}: [model] {key} is missing.")
    return Project(
        root=root,
        kb_path=root / "kb.xlsx",
        materials=root / "materials",
        index_dir=root / "index",
        backups=root / "backups",
        llm=model["llm"],
        embeddings=model["embeddings"],
        gpus=str(model.get("gpus", "0,1")),
        context=int(model.get("context", 32768)),
        candidates=int(run.get("candidates", 20)),
        question_variants=int(run.get("question_variants", 2)),
        not_found=run.get("not_found", "Not found in the sources."),
        headers={**DEFAULT_HEADERS, **data.get("columns", {})},
    )
