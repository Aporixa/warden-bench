from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from corpus.audit import audit_seeds  # noqa: E402


class CorpusAuditTests(unittest.TestCase):
    def test_audit_reports_provenance_gaps_and_duplicates(self) -> None:
        records = [
            {"technique": "one", "prompt": "Same prompt", "source": "<curated:test>"},
            {"technique": "two", "prompt": "  same   PROMPT ", "source": "<curated:test>"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seeds.jsonl"
            path.write_text("".join(json.dumps(record) + "\n" for record in records))
            report = audit_seeds(path)

        self.assertEqual(report["records"], 2)
        self.assertEqual(report["knowledge_tiers"], {"public-generated": 2})
        self.assertEqual(report["duplicate_groups"], [[1, 2]])
        self.assertEqual(report["issue_counts"]["missing-license"], 2)
        self.assertFalse(report["publication_ready"])


if __name__ == "__main__":
    unittest.main()
