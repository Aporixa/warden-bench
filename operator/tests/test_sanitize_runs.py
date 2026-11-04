from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from corpus.sanitize_runs import sanitize_tree  # noqa: E402


class SanitizeRunsTests(unittest.TestCase):
    def test_dry_run_reports_without_rewriting_then_apply_removes_nested_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jsonl = root / "probes.jsonl"
            manifest = root / "manifest.json"
            jsonl.write_text(
                json.dumps({
                    "event": "submit",
                    "response": {
                        "correct": True,
                        "progress_token": "token-one",
                        "progress_token_issued": True,
                    },
                }) + "\n"
            )
            manifest.write_text(json.dumps({
                "safe": True,
                "nested": [{"progress_token": "token-two"}],
            }))
            original = jsonl.read_text()

            self.assertEqual(sanitize_tree(root, apply=False), (2, 2))
            self.assertEqual(jsonl.read_text(), original)

            self.assertEqual(sanitize_tree(root, apply=True), (2, 2))
            self.assertNotIn("progress_token\"", jsonl.read_text())
            self.assertIn("progress_token_issued", jsonl.read_text())
            self.assertNotIn("progress_token", manifest.read_text())
            self.assertEqual(sanitize_tree(root, apply=False), (0, 0))


if __name__ == "__main__":
    unittest.main()
