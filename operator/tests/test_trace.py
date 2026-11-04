from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from core import CampaignTrace, observe_attempt, observation_payload, validate_trace  # noqa: E402


class CampaignTraceTests(unittest.TestCase):
    def test_trace_is_ordered_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaign.jsonl"
            trace = CampaignTrace(path, "campaign-1")
            trace.append("campaign-started", arm="cold")
            observation = observe_attempt("How long?", "It has seven letters.")
            trace.append("observation-recorded", level=4, **observation_payload(observation))
            trace.append("campaign-finished", status="held")

            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([record["sequence"] for record in records], [1, 2, 3])
            self.assertEqual(records[1]["data"]["response_class"], "partial-leak")
            self.assertEqual(validate_trace(path), [])

    def test_existing_trace_is_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaign.jsonl"
            CampaignTrace(path, "campaign-1")
            with self.assertRaises(FileExistsError):
                CampaignTrace(path, "campaign-2")

    def test_unfinished_trace_can_resume_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaign.jsonl"
            trace = CampaignTrace(path, "campaign-1")
            trace.append("campaign-started")
            resumed = CampaignTrace(path, "campaign-1", resume=True)
            record = resumed.append("gate-started", level=2)
            self.assertEqual(record["sequence"], 2)

    def test_resume_recovers_driver_attempt_counters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaign.jsonl"
            trace = CampaignTrace(path, "campaign-1")
            trace.append("campaign-started")
            trace.append(
                "strategy-selected",
                level=5,
                driver="pair",
                driver_attempt=2,
            )

            resumed = CampaignTrace(path, "campaign-1", resume=True)

            self.assertEqual(resumed.driver_attempt_counts(5), {"pair": 2})

    def test_validator_detects_sequence_gap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "campaign.jsonl"
            trace = CampaignTrace(path, "campaign-1")
            trace.append("campaign-started")
            record = json.loads(path.read_text().splitlines()[0])
            record["sequence"] = 2
            path.write_text(json.dumps(record) + "\n")
            self.assertIn("line 1: expected sequence 1", validate_trace(path))


if __name__ == "__main__":
    unittest.main()
