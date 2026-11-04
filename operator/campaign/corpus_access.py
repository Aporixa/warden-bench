"""Fail-closed corpus boundary between outside-in and oracle runs."""

from __future__ import annotations

from pathlib import Path

from .modes import RunMode


def validate_corpus_access(mode: RunMode, path: Path, *, operator_root: Path) -> Path:
    resolved = path.resolve()
    oracle_root = (operator_root / "oracle").resolve()
    is_oracle = resolved == oracle_root or oracle_root in resolved.parents
    if is_oracle and mode != RunMode.AUTHOR_ORACLE:
        raise PermissionError("normal and evaluation runs may not access the author oracle")
    if mode == RunMode.AUTHOR_ORACLE and not is_oracle:
        raise PermissionError("author-oracle mode must use the isolated oracle corpus")
    return resolved
