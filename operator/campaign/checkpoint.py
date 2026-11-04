"""Private, resumable state for one authorized local-lab campaign."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def lab_fingerprint(*, base: str, revision: str | None,
                    models: dict[str, str], lab_run_id: str | None = None,
                    password_fingerprint: str | None = None) -> str:
    """Identify the lab configuration without recording passwords."""

    body = json.dumps(
        {"base": base, "revision": revision, "models": models,
         "lab_run_id": lab_run_id, "password_fingerprint": password_fingerprint},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass
class CampaignCheckpoint:
    run_id: str
    lab_fingerprint: str
    mode: str
    current_level: int = 1
    highest_cleared: int = 0
    progress_token: str | None = None
    target_calls: int = 0
    winning_prompts: dict[str, str] = field(default_factory=dict)
    gate_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    gate_calls: dict[str, int] = field(default_factory=dict)
    hypothesis_observations: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    gates: list[dict[str, Any]] = field(default_factory=list)
    oracle_accessed: bool = False

    def public_summary(self) -> dict[str, Any]:
        """Return checkpoint metadata without the bearer token."""

        out = asdict(self)
        out.pop("progress_token", None)
        return out


class CheckpointStore:
    """Store checkpoints atomically with owner-only permissions."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, run_id: str) -> Path:
        if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
            raise ValueError("invalid checkpoint run id")
        return self.root / f"{run_id}.json"

    def save(self, checkpoint: CampaignCheckpoint) -> Path:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.path_for(checkpoint.run_id)
        temporary = path.with_suffix(".tmp")
        payload = json.dumps(asdict(checkpoint), indent=2, sort_keys=True) + "\n"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        return path

    def load(self, run_id: str, *, expected_lab_fingerprint: str) -> CampaignCheckpoint:
        path = self.path_for(run_id)
        checkpoint = CampaignCheckpoint(**json.loads(path.read_text()))
        if checkpoint.lab_fingerprint != expected_lab_fingerprint:
            raise ValueError(
                "checkpoint lab fingerprint does not match the active lab configuration"
            )
        return checkpoint
