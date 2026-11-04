"""Run-mode boundary for completion, evaluation, and author control runs."""

from __future__ import annotations

from enum import StrEnum


class RunMode(StrEnum):
    COMPLETION = "completion"
    EVALUATION = "evaluation"
    AUTHOR_ORACLE = "author-oracle"


def resolve_run_mode(*, evaluate: bool, author_oracle: bool) -> RunMode:
    """Return one unambiguous mode; oracle access is never implicit."""

    if evaluate and author_oracle:
        raise ValueError("--evaluate and --author-oracle are mutually exclusive")
    if author_oracle:
        return RunMode.AUTHOR_ORACLE
    if evaluate:
        return RunMode.EVALUATION
    return RunMode.COMPLETION
