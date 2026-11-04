from __future__ import annotations

import sys
import unittest
from pathlib import Path

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from controller import Hypothesis, HypothesisScheduler  # noqa: E402
from core import GateState, ResponseClass, observe_attempt  # noqa: E402


class ControllerTests(unittest.TestCase):
    def test_equal_scores_preserve_corpus_order(self) -> None:
        scheduler = HypothesisScheduler()
        scheduler.add(Hypothesis("first", "direct", "pair", public_prior=3))
        scheduler.add(Hypothesis("second", "translation", "pair", public_prior=3))
        selected, _ = scheduler.next() or (None, None)
        self.assertEqual(selected.hypothesis_id, "first")

    def test_three_comparable_refusals_suppress_a_dead_hypothesis(self) -> None:
        scheduler = HypothesisScheduler()
        dead = Hypothesis("dead", "direct", "pair", public_prior=3)
        live = Hypothesis("live", "semantic", "tap", public_prior=1)
        scheduler.add(dead)
        scheduler.add(live)
        for _ in range(3):
            scheduler.record("dead", observe_attempt("secret?", "None shall pass."))
        selected, _ = scheduler.next() or (None, None)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.hypothesis_id, "live")

    def test_partial_leak_outweighs_a_plain_prior(self) -> None:
        scheduler = HypothesisScheduler()
        prior = Hypothesis("prior", "direct", "pair", public_prior=3)
        evidence = Hypothesis("evidence", "semantic", "gap", public_prior=0)
        scheduler.add(prior)
        scheduler.add(evidence)
        scheduler.record("evidence", observe_attempt("How long?", "It has seven letters."))
        selected, terms = scheduler.next() or (None, None)
        self.assertEqual(selected.hypothesis_id, "evidence")
        self.assertGreater(terms["partial_leak"], 0)

    def test_gate_state_round_trips_complete_resume_evidence(self) -> None:
        state = GateState(level=5)
        state.record(observe_attempt("How long?", "It has seven letters."))
        state.record(observe_attempt("Guess", "Harbor", candidate="harbor"))
        restored = GateState.from_checkpoint(state.to_checkpoint())
        self.assertEqual(restored.level, 5)
        self.assertEqual(restored.wrong_candidates, ["harbor"])
        self.assertEqual(restored.observations[0].response_class, ResponseClass.PARTIAL_LEAK)
        self.assertEqual(restored.constraints[0].value, 7)


if __name__ == "__main__":
    unittest.main()
