"""Build a reviewed, time-split dataset from Warden campaign traces."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

OPERATOR = Path(__file__).resolve().parents[1]
if str(OPERATOR) not in sys.path:
    sys.path.insert(0, str(OPERATOR))

from core import classify_technique, validate_trace  # noqa: E402


DATASET_SCHEMA = "warden.campaign-observation"
DATASET_SCHEMA_VERSION = 1
DEFAULT_ARMS = frozenset({
    "public-current",
    "cold",
    "public-unadapted",
    "public-generated",
    "warden-observed",
})
SENSITIVE_KEYS = frozenset({"progress_token"})


@dataclass(frozen=True)
class ReleaseConfig:
    name: str
    version: str
    license_id: str
    cutoff: datetime
    included_arms: frozenset[str] = DEFAULT_ARMS
    allow_empty_split: bool = False


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp must include a UTC offset: {value}")
    return parsed.astimezone(timezone.utc)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")
        records.append(record)
    return records


def load_reviews(path: Path) -> dict[str, dict[str, Any]]:
    """Load explicit human publication decisions keyed by campaign ID."""

    reviews: dict[str, dict[str, Any]] = {}
    for line_number, review in enumerate(_read_jsonl(path), 1):
        campaign_id = str(review.get("campaign_id") or "")
        if not campaign_id:
            raise ValueError(f"{path}:{line_number}: campaign_id is required")
        if campaign_id in reviews:
            raise ValueError(f"{path}:{line_number}: duplicate review for {campaign_id}")
        if not review.get("reviewer") or not review.get("reviewed_at"):
            raise ValueError(f"{path}:{line_number}: reviewer and reviewed_at are required")
        _parse_datetime(str(review["reviewed_at"]))
        reviews[campaign_id] = review
    return reviews


def discover_traces(paths: Iterable[Path]) -> list[Path]:
    """Resolve explicit traces and recursively search supplied directories."""

    traces: set[Path] = set()
    for path in paths:
        if path.is_file():
            traces.add(path.resolve())
        elif path.is_dir():
            traces.update(item.resolve() for item in path.rglob("campaign.jsonl"))
        else:
            raise FileNotFoundError(path)
    return sorted(traces)


def _redact_text(text: str, values: Iterable[str]) -> str:
    redacted = text
    for value in sorted({value for value in values if len(value) >= 3}, key=len, reverse=True):
        redacted = re.sub(re.escape(value), "[REDACTED]", redacted, flags=re.IGNORECASE)
    return redacted


def _redact(value: Any, secrets: Iterable[str]) -> Any:
    if isinstance(value, str):
        return _redact_text(value, secrets)
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, dict):
        return {
            key: _redact(item, secrets)
            for key, item in value.items()
            if key not in SENSITIVE_KEYS
        }
    return value


def compile_release(
    trace_paths: Iterable[Path],
    reviews: dict[str, dict[str, Any]],
    config: ReleaseConfig,
    *,
    secrets: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compile publishable observations, exclusions, and source identities."""

    observations: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    for path in trace_paths:
        errors = validate_trace(path)
        records = _read_jsonl(path)
        campaign_id = str(records[0].get("campaign_id") if records else path.name)
        if errors:
            exclusions.append({"campaign_id": campaign_id, "reason": "invalid-trace", "errors": errors})
            continue
        started = next((record for record in records if record["event_type"] == "campaign-started"), None)
        finished = next((record for record in records if record["event_type"] == "campaign-finished"), None)
        if not started or not finished:
            exclusions.append({"campaign_id": campaign_id, "reason": "incomplete-campaign"})
            continue
        start_data = started["data"]
        arm = str(start_data.get("knowledge_arm") or "")
        if arm not in config.included_arms:
            exclusions.append({"campaign_id": campaign_id, "reason": "excluded-knowledge-arm", "arm": arm})
            continue
        review = reviews.get(campaign_id)
        if not review or review.get("allow_publish") is not True:
            exclusions.append({"campaign_id": campaign_id, "reason": "publication-review-required"})
            continue

        started_at = _parse_datetime(str(started["recorded_at"]))
        split = "training" if started_at < config.cutoff else "heldout"
        campaign_secrets = list(secrets)
        for record in records:
            data = record.get("data", {})
            if record.get("event_type") == "observation-recorded" and data.get("verified") and data.get("candidate"):
                campaign_secrets.append(str(data["candidate"]))

        source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        sources.append({
            "campaign_id": campaign_id,
            "knowledge_arm": arm,
            "sha256": source_sha,
            "reviewer": review["reviewer"],
            "reviewed_at": review["reviewed_at"],
        })
        for record in records:
            if record.get("event_type") != "observation-recorded":
                continue
            data = dict(record["data"])
            if not data.get("technique"):
                data["technique"] = classify_technique(
                    str(data.get("attempt") or data.get("prompt") or ""),
                    driver=str(data.get("driver") or "") or None,
                ).to_dict()
            sanitized = _redact(data, campaign_secrets)
            observations.append({
                "schema": DATASET_SCHEMA,
                "schema_version": DATASET_SCHEMA_VERSION,
                "release": {"name": config.name, "version": config.version},
                "split": split,
                "campaign_id": campaign_id,
                "campaign_started_at": started["recorded_at"],
                "knowledge_arm": arm,
                "defense_revision": start_data.get("defense_revision"),
                "budget": start_data.get("budget"),
                "source": {"trace_sha256": source_sha, "event_sequence": record["sequence"]},
                **sanitized,
            })

    return observations, exclusions, sources


def write_release(
    output: Path,
    observations: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    config: ReleaseConfig,
) -> dict[str, Any]:
    """Write a new release directory without replacing existing data."""

    if not observations:
        raise ValueError("no reviewed observations are eligible for release")
    split_counts = Counter(record["split"] for record in observations)
    if not config.allow_empty_split and ({"training", "heldout"} - split_counts.keys()):
        raise ValueError("release requires both training and heldout observations")
    output.mkdir(parents=True, exist_ok=False)
    observations_path = output / "observations.jsonl"
    observations_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in observations),
        encoding="utf-8",
    )
    (output / "exclusions.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in exclusions),
        encoding="utf-8",
    )
    response_counts = Counter(record.get("response_class", "unknown") for record in observations)
    manifest = {
        "schema": "warden.dataset-release",
        "schema_version": 1,
        "name": config.name,
        "version": config.version,
        "license": config.license_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "temporal_cutoff": config.cutoff.isoformat(),
        "included_knowledge_arms": sorted(config.included_arms),
        "observed_knowledge_arms": sorted({source["knowledge_arm"] for source in sources}),
        "observation_count": len(observations),
        "campaign_count": len(sources),
        "split_counts": dict(split_counts),
        "response_class_counts": dict(response_counts),
        "source_campaigns": sources,
        "excluded_campaign_count": len(exclusions),
        "observations_sha256": hashlib.sha256(observations_path.read_bytes()).hexdigest(),
        "human_review_required": True,
        "structural_leaks_may_remain": True,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    dataset_card = f"""# {config.name} {config.version}

This release contains reviewed observations from Warden Bench adaptive campaigns.

## Scope

- License: `{config.license_id}`
- Temporal cutoff: `{config.cutoff.isoformat()}`
- Campaigns: {manifest["campaign_count"]}
- Observations: {manifest["observation_count"]}
- Training observations: {split_counts.get("training", 0)}
- Held-out observations: {split_counts.get("heldout", 0)}
- Knowledge arms: {", ".join(manifest["observed_knowledge_arms"])}

The temporal split assigns each complete campaign according to its start time. The release does not split observations from one campaign across both sets.

## Review and redaction

Every included campaign has a named publication review. The builder redacts exact secrets supplied during release construction and verified candidates recorded by the campaign.

Exact-value redaction does not remove every structural disclosure. Acrostics, encodings, letter positions, and inferred constraints may remain because those observations are part of the defensive research record.

## Intended use

Use this release to study adaptive attack behavior, information exposed by defenses, and changes between defense revisions. Do not treat the release as a collection of guaranteed exploits or as evidence about targets outside the declared capability profile.

## Source identity

`manifest.json` records each source campaign hash, reviewer identity, schema version, license, cutoff, and output hash. `exclusions.jsonl` records campaigns that did not enter this release.
"""
    (output / "DATASET.md").write_text(dataset_card, encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, nargs="+", help="campaign trace or directory to search")
    parser.add_argument("--reviews", type=Path, required=True, help="JSONL publication review decisions")
    parser.add_argument("--output", type=Path, required=True, help="new release directory")
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--license", dest="license_id", required=True)
    parser.add_argument("--cutoff", required=True, help="ISO 8601 temporal split cutoff")
    parser.add_argument("--secret-file", type=Path, help="one exact secret value per line")
    parser.add_argument(
        "--author-oracle-only",
        action="store_true",
        help="build a separate release that contains only author-oracle campaigns",
    )
    parser.add_argument("--allow-empty-split", action="store_true")
    args = parser.parse_args(argv)

    included_arms = {"author-oracle"} if args.author_oracle_only else set(DEFAULT_ARMS)
    config = ReleaseConfig(
        name=args.name,
        version=args.version,
        license_id=args.license_id,
        cutoff=_parse_datetime(args.cutoff),
        included_arms=frozenset(included_arms),
        allow_empty_split=args.allow_empty_split,
    )
    secrets = []
    if args.secret_file:
        secrets = [line.strip() for line in args.secret_file.read_text().splitlines() if line.strip()]
    trace_paths = discover_traces(args.trace)
    observations, exclusions, sources = compile_release(
        trace_paths,
        load_reviews(args.reviews),
        config,
        secrets=secrets,
    )
    manifest = write_release(args.output, observations, exclusions, sources, config)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
