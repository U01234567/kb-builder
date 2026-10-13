"""Ask the model which passages carry the answer, then for the answer itself; check every quote.

`chat` is any function (prompt, schema) -> dict, so all of this runs in tests without a model.
"""

import re
import unicodedata
from dataclasses import dataclass
from string import Template

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"verdicts": {"type": "array", "items": {
        "type": "object",
        "properties": {"n": {"type": "integer"}, "carries_answer": {"type": "boolean"}, "reason": {"type": "string"}},
        "required": ["n", "carries_answer", "reason"]}}},
    "required": ["verdicts"],
}


@dataclass(frozen=True)
class Result:
    """A generated answer: the answer, a simpler version, other phrasings, and (Candidate, quote) pairs."""

    answer: str
    answer_simple: str
    question_variants: tuple
    evidence: tuple


def answer_schema(variants: int) -> dict:
    """The JSON shape the answer must have, with exactly `variants` question variants."""
    text = {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "answer": text,
            "answer_simple": text,
            "question_variants": {"type": "array", "items": text, "minItems": variants, "maxItems": variants},
            "evidence": {"type": "array", "items": {
                "type": "object", "properties": {"n": {"type": "integer"}, "quote": text}, "required": ["n", "quote"]}},
        },
        "required": ["answer", "answer_simple", "question_variants", "evidence"],
    }


def numbered(candidates: list, titles: dict) -> str:
    """The passages as the model sees them: '[n] title — location', then the text."""
    return "\n\n".join(f"[{n}] {titles.get(c.fingerprint, '')} — {c.location}\n{c.text}"
                       for n, c in enumerate(candidates, start=1))


def judge(chat, template: str, question: str, candidates: list, titles: dict) -> list:
    """The candidates the model says carry the answer, in their original order."""
    if not candidates:
        return []
    prompt = Template(template).substitute(question=question, passages=numbered(candidates, titles))
    keep = {v["n"] for v in chat(prompt, JUDGE_SCHEMA)["verdicts"] if v["carries_answer"]}
    return [c for n, c in enumerate(candidates, start=1) if n in keep]


def write(chat, template: str, question: str, kept: list, titles: dict, variants: int, not_found: str) -> Result:
    """The answer, written from the kept passages only. No kept passages: `not_found`, without a model call.

    Evidence that points at a passage number the model was not given is dropped.
    """
    if not kept:
        return Result(not_found, not_found, (), ())
    prompt = Template(template).substitute(question=question, passages=numbered(kept, titles), variants=variants)
    data = chat(prompt, answer_schema(variants))
    evidence = tuple((kept[e["n"] - 1], e["quote"].strip()) for e in data["evidence"] if 1 <= e["n"] <= len(kept))
    return Result(data["answer"].strip(), data["answer_simple"].strip(),
                  tuple(v.strip() for v in data["question_variants"][:variants]), evidence)


def normalize(text: str) -> str:
    """Text without the differences a quote may innocently have: curly quotes, dashes, spacing, case."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans("‘’‚“”„–—", "'''\"\"\"--"))
    return re.sub(r"\s+", " ", text).strip().casefold()


def verify(quote: str, source_text: str) -> bool:
    """True when every part of the quote (split at '...') appears literally in the source, in order."""
    haystack = normalize(source_text)
    position = 0
    parts = [p.strip() for p in re.split(r"\.\.\.|…", normalize(quote)) if p.strip()]
    for part in parts:
        position = haystack.find(part, position)
        if position < 0:
            return False
        position += len(part)
    return bool(parts)
