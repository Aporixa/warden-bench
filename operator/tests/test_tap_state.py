from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from core import GateState  # noqa: E402
from tap import tap  # noqa: E402


class TapStateTests(unittest.TestCase):
    def test_repeated_attempts_share_gate_evidence(self) -> None:
        state = GateState(level=4)
        responses = iter(("It has seven letters.", "The first sound is s."))

        def fake_branch(brief, history, branch, received_state):
            self.assertIs(received_state, state)
            return ["structural probe"]

        def fake_chat(level, prompt):
            return tap.ChatResult(level, prompt, next(responses), 200)

        with (
            patch.object(tap, "branch_attacks", side_effect=fake_branch),
            patch.object(tap, "chat", side_effect=fake_chat),
            patch.object(tap, "judge_extract", return_value=None),
            patch.object(tap, "TARGET_SLEEP_S", 0),
        ):
            first = tap.run_tap(4, branch=1, width=1, depth=1, state=state)
            second = tap.run_tap(4, branch=1, width=1, depth=1, state=state)

        self.assertIs(first.gate_state, state)
        self.assertIs(second.gate_state, state)
        self.assertEqual(len(state.observations), 2)
        self.assertEqual(
            [(e.kind, e.value) for e in state.constraints],
            [("length", 7), ("prefix", "s")],
        )


if __name__ == "__main__":
    unittest.main()
