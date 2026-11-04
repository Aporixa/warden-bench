from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from core import Evidence, Observation, ResponseClass  # noqa: E402
import pair.pair as P  # noqa: E402


class PairTests(unittest.TestCase):
    def test_grounded_semantic_candidate_stops_the_linear_loop(self) -> None:
        observation = Observation(
            prompt="define it",
            response="A Tagetes flower.",
            family="semantic-context",
            response_class=ResponseClass.PARTIAL_LEAK,
            evidence=[Evidence("candidate-secret", "marigold", 0.8,
                               "semantic-analyst")],
        )
        submit_calls: list[str] = []

        def submit(_: int, candidate: str) -> dict:
            submit_calls.append(candidate)
            return {"correct": candidate == "marigold", "progress_token": "next"}

        brief = P.T.AttackerBrief(level=5, defenses_in_force="unknown")
        with patch.object(P.T, "branch_attacks", return_value=["define it"]), \
             patch.object(P.T, "chat", return_value=SimpleNamespace(response="A Tagetes flower.")), \
             patch.object(P.T, "judge_extract", return_value=None), \
             patch.object(P.T, "submit", side_effect=submit), \
             patch.object(P.T, "TARGET_SLEEP_S", 0), \
             patch.object(P, "observe_attempt", return_value=observation):
            result = P.run_pair(5, brief, turns=5)

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.target_calls, 1)
        self.assertEqual(submit_calls, ["marigold"])


if __name__ == "__main__":
    unittest.main()
