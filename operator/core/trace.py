"""Versioned, append-only campaign traces for Warden Bench research."""
from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence import Observation
from .taxonomy import TechniqueClassification


TRACE_SCHEMA = "warden.campaign-trace"
TRACE_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def observation_payload(
    observation: Observation,
    *,
    classification: TechniqueClassification | None = None,
) -> dict[str, Any]:
    """Return the stable trace representation of an observation."""

    return {
        "attempt": observation.prompt,
        "response": observation.response,
        "technique_family": observation.family,
        "technique": classification.to_dict() if classification else None,
        "response_class": observation.response_class.value,
        "evidence": [asdict(item) for item in observation.evidence],
        "candidate": observation.candidate,
        "verified": observation.correct,
        "error": observation.error,
    }


class CampaignTrace:
    """Create one trace and append ordered events to it.

    The trace refuses to replace an existing file. Each append opens, flushes,
    and synchronizes the file so a stopped campaign retains completed events.
    Raw target text is preserved and must be sanitized before publication.
    """

    def __init__(self, path: Path, campaign_id: str, *, resume: bool = False) -> None:
        self.path = path
        self.campaign_id = campaign_id
        self._sequence = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        if not resume:
            with path.open("x", encoding="utf-8"):
                pass
            return
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if not records:
            raise ValueError("cannot resume an empty campaign trace")
        if any(record.get("campaign_id") != campaign_id for record in records):
            raise ValueError("campaign trace id does not match checkpoint")
        if records[-1].get("event_type") == "campaign-finished":
            raise ValueError("cannot resume a finished campaign trace")
        self._sequence = int(records[-1]["sequence"])

    def append(self, event_type: str, **data: Any) -> dict[str, Any]:
        """Append one event and return the exact record written."""

        if not event_type or not event_type.replace("-", "").isalnum():
            raise ValueError("event_type must contain letters, digits, or hyphens")
        self._sequence += 1
        record = {
            "schema": TRACE_SCHEMA,
            "schema_version": TRACE_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "sequence": self._sequence,
            "recorded_at": _utc_now(),
            "event_type": event_type,
            "data": data,
        }
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return record

    def driver_attempt_counts(self, level: int) -> Counter[str]:
        """Return the highest recorded attempt number per driver at a gate."""

        counts: Counter[str] = Counter()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            data = record.get("data", {})
            if record.get("event_type") != "strategy-selected" or data.get("level") != level:
                continue
            driver = str(data.get("driver") or "")
            attempt = data.get("driver_attempt")
            if driver and isinstance(attempt, int):
                counts[driver] = max(counts[driver], attempt)
        return counts


def validate_trace(path: Path) -> list[str]:
    """Return structural errors without interpreting research outcomes."""

    errors: list[str] = []
    campaign_id: str | None = None
    expected_sequence = 1
    started = False
    finished = False
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
            continue
        if record.get("schema") != TRACE_SCHEMA:
            errors.append(f"line {line_number}: unsupported schema")
        if record.get("schema_version") != TRACE_SCHEMA_VERSION:
            errors.append(f"line {line_number}: unsupported schema_version")
        current_id = record.get("campaign_id")
        if campaign_id is None:
            campaign_id = current_id
        elif current_id != campaign_id:
            errors.append(f"line {line_number}: campaign_id changed")
        if record.get("sequence") != expected_sequence:
            errors.append(f"line {line_number}: expected sequence {expected_sequence}")
        expected_sequence += 1
        event_type = record.get("event_type")
        if event_type == "campaign-started":
            if started:
                errors.append(f"line {line_number}: duplicate campaign-started")
            started = True
        elif event_type == "campaign-finished":
            finished = True
        elif not started:
            errors.append(f"line {line_number}: event precedes campaign-started")
        if finished and event_type != "campaign-finished":
            errors.append(f"line {line_number}: event follows campaign-finished")
    if expected_sequence == 1:
        errors.append("trace is empty")
    elif not started:
        errors.append("trace has no campaign-started event")
    return errors
