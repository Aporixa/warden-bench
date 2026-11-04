from __future__ import annotations

import sys
import unittest
from pathlib import Path

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from seedlib import (  # noqa: E402
    KnowledgeTier,
    classify_seed,
    load_seeds,
    seeds_through_tier,
)


class SeedProvenanceTests(unittest.TestCase):
    def test_legacy_sources_are_classified_conservatively(self) -> None:
        self.assertEqual(
            classify_seed({"source": "<curated:deepteam-inspired>"}),
            KnowledgeTier.PUBLIC_GENERATED,
        )
        self.assertEqual(
            classify_seed({"source": "warden-probes-7.jsonl"}),
            KnowledgeTier.WARDEN_OBSERVED,
        )
        self.assertEqual(
            classify_seed({"source": "manual:cross-level-confirmation", "manual": True}),
            KnowledgeTier.AUTHOR_ORACLE,
        )
        self.assertEqual(
            classify_seed({"source": "unreviewed.jsonl"}),
            KnowledgeTier.AUTHOR_ORACLE,
        )

    def test_public_unadapted_requires_an_explicit_tag(self) -> None:
        seeds = [
            {"knowledge_tier": "public-unadapted", "prompt": "a", "technique": "x"},
            {"source": "<curated:deepteam-inspired>", "prompt": "b", "technique": "y"},
        ]

        selected = seeds_through_tier(seeds, KnowledgeTier.PUBLIC_UNADAPTED)

        self.assertEqual([seed["prompt"] for seed in selected], ["a"])

    def test_invalid_explicit_tier_fails_loudly(self) -> None:
        with self.assertRaises(ValueError):
            classify_seed({"knowledge_tier": "public-ish"})

    def test_current_corpus_has_no_claimed_unadapted_upstream_seeds(self) -> None:
        seeds = load_seeds(OPERATOR / "seeds.jsonl")
        counts = {tier: 0 for tier in KnowledgeTier}
        for seed in seeds:
            counts[classify_seed(seed)] += 1

        self.assertEqual(counts[KnowledgeTier.PUBLIC_UNADAPTED], 0)
        self.assertEqual(counts[KnowledgeTier.PUBLIC_GENERATED], 20)
        self.assertEqual(counts[KnowledgeTier.WARDEN_OBSERVED], 30)
        self.assertEqual(counts[KnowledgeTier.AUTHOR_ORACLE], 2)


if __name__ == "__main__":
    unittest.main()
