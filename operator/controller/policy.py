"""Evidence-scored hypothesis queue used by the completion operator."""

from __future__ import annotations

from dataclasses import dataclass, field

from core import Observation, ResponseClass


@dataclass
class Hypothesis:
    hypothesis_id: str
    family: str
    strategy: str
    prompt: str = ""
    public_prior: float = 0.0
    previous_gate_transfer: float = 0.0
    estimated_cost: int = 1
    observations: list[Observation] = field(default_factory=list)
    disabled: bool = False

    @property
    def comparable_refusals(self) -> int:
        return sum(o.response_class == ResponseClass.REFUSAL for o in self.observations)

    @property
    def suppressed(self) -> bool:
        if self.disabled:
            return True
        if self.has_progress:
            return False
        unproductive = sum(o.response_class in {
            ResponseClass.ENGAGED,
            ResponseClass.REFUSAL,
            ResponseClass.WRONG_CANDIDATE,
            ResponseClass.INPUT_REJECTED,
        } for o in self.observations)
        return self.comparable_refusals >= 3 or unproductive >= 5

    @property
    def has_progress(self) -> bool:
        return any(o.response_class in {
            ResponseClass.GUARD_BLOCK,
            ResponseClass.PARTIAL_LEAK,
            ResponseClass.VERIFIED,
        } for o in self.observations)


class HypothesisScheduler:
    """Rank hypotheses from observable evidence and record every score term."""

    def __init__(self) -> None:
        self._items: dict[str, Hypothesis] = {}

    def add(self, hypothesis: Hypothesis) -> None:
        if hypothesis.hypothesis_id in self._items:
            raise ValueError(f"duplicate hypothesis id: {hypothesis.hypothesis_id}")
        self._items[hypothesis.hypothesis_id] = hypothesis

    def record(self, hypothesis_id: str, observation: Observation) -> None:
        self._items[hypothesis_id].observations.append(observation)

    def __contains__(self, hypothesis_id: str) -> bool:
        return hypothesis_id in self._items

    def score_terms(self, hypothesis: Hypothesis) -> dict[str, float]:
        engaged = sum(o.response_class == ResponseClass.ENGAGED for o in hypothesis.observations)
        partial = sum(o.response_class == ResponseClass.PARTIAL_LEAK for o in hypothesis.observations)
        blocked = sum(o.response_class == ResponseClass.GUARD_BLOCK for o in hypothesis.observations)
        wrong = sum(o.response_class == ResponseClass.WRONG_CANDIDATE for o in hypothesis.observations)
        return {
            "public_prior": hypothesis.public_prior,
            "previous_gate_transfer": hypothesis.previous_gate_transfer,
            "engagement": engaged * 0.5,
            "partial_leak": partial * 4.0,
            "guard_block": blocked * 5.0,
            "wrong_candidate": wrong * -1.0,
            "refusal_penalty": hypothesis.comparable_refusals * -3.0,
            "cost_penalty": max(hypothesis.estimated_cost - 1, 0) * -0.1,
            "attempt_penalty": len(hypothesis.observations) * -0.25,
        }

    def score(self, hypothesis: Hypothesis) -> float:
        return sum(self.score_terms(hypothesis).values())

    def next(self) -> tuple[Hypothesis, dict[str, float]] | None:
        candidates = [item for item in self._items.values() if not item.suppressed]
        if not candidates:
            return None
        selected = max(
            candidates,
            key=lambda item: (self.score(item), -len(item.observations)),
        )
        return selected, self.score_terms(selected)
