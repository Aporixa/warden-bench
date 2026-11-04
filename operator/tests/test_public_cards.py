from __future__ import annotations

import sys
import unittest
from pathlib import Path

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from corpus.public_cards import validate_public_corpus  # noqa: E402


class PublicCardTests(unittest.TestCase):
    def test_reviewed_public_corpus_is_internally_consistent(self) -> None:
        public = OPERATOR / "corpus" / "public"
        self.assertEqual(
            validate_public_corpus(public / "sources.jsonl", public / "techniques.jsonl"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
