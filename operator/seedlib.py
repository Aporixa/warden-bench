"""
Shared seed-corpus loader for the Warden red-team drivers (TAP, GAP,
Crescendo).

Seeds are exemplars of attacks that have worked — or have been
curated as promising — against the lab. Each driver loads them on
every attacker call and injects them into the user message so
techniques discovered in one search transfer into the next, and
across levels.

Cross-level by design: a defensive-framing bypass first observed on
L8 is also a candidate angle on weaker levels, since the underlying
target weaknesses (literal-string output filter ignoring interleaved
separators, persona refusal that can be reframed as
co-conspiracy, etc.) are shared across the level stack.

Schema (one JSON object per line, '#' comments and blank lines OK):
  required: technique, prompt
  optional: level, leak_form, why, rejected_prompt, rejected_lesson,
            source, password, manual, knowledge_tier

`manual: true` marks an entry as hand-curated. The build_seeds.py
regenerator preserves these across rebuilds; everything else is
derived from warden-corpus.json.

Drivers do their own block-rendering — Crescendo wants different
framing than TAP/GAP — so this module only handles loading.
"""
from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path


class KnowledgeTier(StrEnum):
    """How much Warden-specific knowledge a seed carries."""

    PUBLIC_UNADAPTED = "public-unadapted"
    PUBLIC_GENERATED = "public-generated"
    WARDEN_OBSERVED = "warden-observed"
    AUTHOR_ORACLE = "author-oracle"


def classify_seed(seed: dict[str, object]) -> KnowledgeTier:
    """Classify legacy seeds conservatively unless explicitly tagged."""

    explicit = seed.get("knowledge_tier")
    if explicit:
        try:
            return KnowledgeTier(str(explicit))
        except ValueError as exc:
            raise ValueError(f"unknown seed knowledge_tier: {explicit}") from exc
    if seed.get("manual"):
        return KnowledgeTier.AUTHOR_ORACLE
    source = str(seed.get("source") or "")
    if source.startswith("<curated:"):
        # These are local adaptations of public work, not upstream records.
        return KnowledgeTier.PUBLIC_GENERATED
    if source.startswith("warden-probes-"):
        return KnowledgeTier.WARDEN_OBSERVED
    # Unknown legacy provenance is not safe to call public.
    return KnowledgeTier.AUTHOR_ORACLE


def seeds_through_tier(
    seeds: list[dict[str, object]],
    tier: KnowledgeTier,
) -> list[dict[str, object]]:
    """Return seeds available at or below a knowledge tier."""

    order = {
        KnowledgeTier.PUBLIC_UNADAPTED: 0,
        KnowledgeTier.PUBLIC_GENERATED: 1,
        KnowledgeTier.WARDEN_OBSERVED: 2,
        KnowledgeTier.AUTHOR_ORACLE: 3,
    }
    ceiling = order[tier]
    return [seed for seed in seeds if order[classify_seed(seed)] <= ceiling]


def load_seeds(path: Path) -> list[dict[str, object]]:
    """Read a seeds.jsonl file. Missing file -> empty list (opt-in).
    Malformed lines and entries missing required keys are skipped
    silently; a bad line shouldn't crash a sweep."""
    if not path.exists():
        return []
    out: list[dict[str, object]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not all(k in entry for k in ("technique", "prompt")):
            continue
        out.append(entry)
    return out
