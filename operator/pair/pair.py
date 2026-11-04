"""First-class PAIR driver sharing the ladder's target and evidence state.

PAIR performs linear refinement: each attacker call sees the complete evidence
from earlier attempts at the gate and emits one new prompt. TAP and GAP remain
available when the controller decides breadth or graph memory is warranted.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from core import (AdaptiveSelectionPolicy, GateState, ResponseClass,
                  grounded_candidate, observe_attempt)
import tap.tap as T


@dataclass
class PairResult:
    level: int
    status: str
    target_calls: int
    attempts: list[dict[str, Any]]
    winning_prompt: str | None = None
    best_score: int | None = None
    error: str | None = None


def run_pair(level: int, brief: T.AttackerBrief, *, turns: int = 5,
             focus: str = "",
             state: GateState | None = None,
             policy: AdaptiveSelectionPolicy | None = None) -> PairResult:
    """Run up to ``turns`` sequential prompt refinements against one gate."""

    if turns < 1:
        raise ValueError("PAIR turns must be at least 1")
    state = state or GateState(level=level)
    if state.level != level:
        raise ValueError(f"gate state is for level {state.level}, not {level}")
    policy = policy or AdaptiveSelectionPolicy()
    if focus:
        brief = T.AttackerBrief(
            level=brief.level,
            defenses_in_force=brief.defenses_in_force,
            open_surface=brief.open_surface,
            extra=(brief.extra + "\n\nCURRENT HYPOTHESIS TO TEST:\n" + focus).strip(),
        )
    history: list[T.TapNode] = []
    attempts: list[dict[str, Any]] = []
    best_score: int | None = None

    for turn in range(1, turns + 1):
        prompts = T.branch_attacks(brief, history, 1, state)
        if not prompts:
            return PairResult(level, "NO-EXPAND", len(attempts), attempts,
                              best_score=best_score, error="attacker returned no prompt")
        prompt = prompts[0]
        try:
            chat = T.chat(level, prompt)
        except Exception as exc:
            return PairResult(level, "ATTACKER-ERROR", len(attempts), attempts,
                              best_score=best_score,
                              error=f"{type(exc).__name__}: {exc}")

        candidate = T.judge_extract(
            chat.response,
            level,
            wrong_already=state.wrong_candidates or None,
        )
        correct = False
        if candidate:
            verdict = T.submit(level, candidate)
            correct = bool(verdict.get("correct"))
        observation = observe_attempt(
            prompt,
            chat.response,
            candidate=candidate,
            correct=correct,
        )
        if not candidate:
            candidate = grounded_candidate(observation)
            if candidate and candidate not in state.wrong_candidates:
                verdict = T.submit(level, candidate)
                correct = bool(verdict.get("correct"))
                observation.candidate = candidate
                observation.correct = correct
                observation.response_class = (
                    ResponseClass.VERIFIED if correct
                    else ResponseClass.WRONG_CANDIDATE
                )
        state.record(observation)
        score, reason = policy.score(observation)
        best_score = max(best_score or score, score)
        node = T.TapNode(
            layer=turn,
            prompt=prompt,
            response=chat.response,
            score=score,
            score_reason=reason,
            candidate=candidate,
            correct=correct,
            parent=history[-1] if history else None,
            observation=observation,
        )
        history.append(node)
        attempts.append({
            "turn": turn,
            "prompt": prompt,
            "response": chat.response,
            "candidate": candidate,
            "correct": correct,
            "score": score,
            "score_reason": reason,
        })
        if correct:
            return PairResult(level, "PASS", len(attempts), attempts,
                              winning_prompt=prompt, best_score=score)
        time.sleep(T.TARGET_SLEEP_S)

    return PairResult(level, "FAIL", len(attempts), attempts, best_score=best_score)
