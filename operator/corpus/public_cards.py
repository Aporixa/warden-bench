"""Validate the reviewed public source registry and technique-card corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def validate_public_corpus(sources_path: Path, cards_path: Path) -> list[str]:
    errors: list[str] = []
    sources = _load(sources_path)
    cards = _load(cards_path)
    source_ids = [str(row.get("source_id") or "") for row in sources]
    card_ids = [str(row.get("card_id") or "") for row in cards]
    if len(source_ids) != len(set(source_ids)):
        errors.append("source_id values must be unique")
    if len(card_ids) != len(set(card_ids)):
        errors.append("card_id values must be unique")
    known_sources = set(source_ids)
    for index, source in enumerate(sources, 1):
        for field in ("source_id", "version", "retrieved_at", "source_url", "license",
                      "review_status", "payloads_copied"):
            if field not in source:
                errors.append(f"source {index} lacks {field}")
    for index, card in enumerate(cards, 1):
        for field in ("card_id", "technique", "prompt", "objective", "orchestration",
                      "required_capabilities", "expected_signal", "pivot_on", "source_ids",
                      "knowledge_tier", "created_at", "license"):
            if field not in card:
                errors.append(f"card {index} lacks {field}")
        if card.get("knowledge_tier") != "public-generated":
            errors.append(f"card {index} is not public-generated")
        unknown = set(card.get("source_ids") or []) - known_sources
        if unknown:
            errors.append(f"card {index} has unknown source_ids: {sorted(unknown)}")
        source_text = json.dumps(card.get("source_ids") or []).lower()
        if "warden" in source_text or "oracle" in source_text:
            errors.append(f"card {index} cites target-specific material")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path)
    parser.add_argument("cards", type=Path)
    args = parser.parse_args()
    errors = validate_public_corpus(args.sources, args.cards)
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
