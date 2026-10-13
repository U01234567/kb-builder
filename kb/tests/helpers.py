"""A throwaway project on disk, and an embedding function that needs no model."""

import hashlib
import shutil
from pathlib import Path

from openpyxl import Workbook

from kb import project

FIXTURES = Path(__file__).parent / "fixtures"


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Bag of words in 64 buckets: texts sharing words get similar vectors."""
    vectors = []
    for text in texts:
        vector = [0.0] * 64
        for word in text.lower().split():
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1
        vectors.append(vector)
    return vectors


def make_project(root: Path, topics: dict[str, list[str]], files: dict[str, str]):
    """project.toml, materials (relative path -> fixture name) and a kb.xlsx with one sheet per topic."""
    (root / "materials").mkdir(parents=True)
    (root / "project.toml").write_text('[model]\nllm = "fake"\nembeddings = "fake"\n', encoding="utf-8")
    for path, fixture in files.items():
        (root / "materials" / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / fixture, root / "materials" / path)
    wb = Workbook()
    wb.remove(wb.active)
    for topic, questions in topics.items():
        sheet = wb.create_sheet(topic)
        sheet.append(["Question"])
        for question in questions:
            sheet.append([question])
    wb.save(root / "kb.xlsx")
    return project.load(root)
