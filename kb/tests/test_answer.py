"""answer.py: judging passages, writing the answer, and checking quotes, with a fake model."""

from unittest import TestCase

from kb import answer
from kb.index import Candidate

FIRST = Candidate("f1", "Parking › Rate", "The rate is 2,50 per hour.")
SECOND = Candidate("f2", "p. 3", "Unrelated text about cycling.")


def fake_chat(prompt, schema):
    """Keeps passage 1, and answers with one true and one made-up quote."""
    if "verdicts" in schema["properties"]:
        return {"verdicts": [{"n": 1, "carries_answer": True, "reason": "rate"},
                            {"n": 2, "carries_answer": False, "reason": "cycling"}]}
    return {"answer": "2,50 per hour.", "answer_simple": "2,50 an hour.", "question_variants": ["How high?", "What rate?", "extra"],
            "evidence": [{"n": 1, "quote": "rate is 2,50"}, {"n": 9, "quote": "out of range"}]}


class Judge(TestCase):
    def test_keeps_only_what_carries_the_answer(self):
        self.assertEqual(answer.judge(fake_chat, "$question $passages", "Rate?", [FIRST, SECOND], {}), [FIRST])

    def test_no_candidates_means_no_model_call(self):
        self.assertEqual(answer.judge(None, "$question $passages", "Rate?", [], {}), [])


class Write(TestCase):
    def test_uses_the_kept_passages_and_drops_unknown_evidence(self):
        result = answer.write(fake_chat, "$question $passages $variants", "Rate?", [FIRST], {}, 2, "Not found")
        self.assertEqual(result.question_variants, ("How high?", "What rate?"))
        self.assertEqual(result.evidence, ((FIRST, "rate is 2,50"),))

    def test_nothing_kept_means_not_found(self):
        self.assertEqual(answer.write(None, "", "Rate?", [], {}, 2, "Not found").answer, "Not found")


class Verify(TestCase):
    def test_literal_quote(self):
        self.assertTrue(answer.verify("rate is 2,50", FIRST.text))

    def test_quote_with_other_spacing_case_and_quote_marks(self):
        self.assertTrue(answer.verify("“The  RATE is 2,50”".strip("“”"), "The rate is 2,50 per hour."))

    def test_quote_with_an_ellipsis(self):
        self.assertTrue(answer.verify("The rate … per hour.", FIRST.text))

    def test_made_up_quote(self):
        self.assertFalse(answer.verify("The rate is 3,00", FIRST.text))

    def test_empty_quote(self):
        self.assertFalse(answer.verify("", FIRST.text))
