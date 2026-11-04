from __future__ import annotations

import stat
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

OPERATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPERATOR))

from campaign import (  # noqa: E402
    CampaignCheckpoint,
    CheckpointStore,
    RunMode,
    resolve_run_mode,
    validate_corpus_access,
)

_LADDER_SPEC = importlib.util.spec_from_file_location(
    "warden_ladder_cli", OPERATOR / "ladder" / "ladder.py"
)
assert _LADDER_SPEC and _LADDER_SPEC.loader
_LADDER = importlib.util.module_from_spec(_LADDER_SPEC)
_LADDER_SPEC.loader.exec_module(_LADDER)


class CampaignBoundaryTests(unittest.TestCase):
    def test_cli_defaults_to_pair_led_l1_through_l7_completion(self) -> None:
        args = _LADDER.parse_args([])
        self.assertEqual(args.chain, ["pair", "tap", "gap"])
        self.assertEqual(args.max_level, 7)
        self.assertFalse(args.author_oracle)
        self.assertFalse(args.evaluate)

    def test_default_mode_is_completion(self) -> None:
        self.assertEqual(
            resolve_run_mode(evaluate=False, author_oracle=False),
            RunMode.COMPLETION,
        )

    def test_oracle_requires_its_explicit_mode(self) -> None:
        oracle = OPERATOR / "oracle" / "current.jsonl"
        with self.assertRaises(PermissionError):
            validate_corpus_access(RunMode.COMPLETION, oracle, operator_root=OPERATOR)
        self.assertEqual(
            validate_corpus_access(RunMode.AUTHOR_ORACLE, oracle, operator_root=OPERATOR),
            oracle.resolve(),
        )

    def test_modes_are_mutually_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            resolve_run_mode(evaluate=True, author_oracle=True)

    def test_resume_restores_evidence_earned_hard_gate_limit(self) -> None:
        self.assertEqual(
            _LADDER.restored_gate_cap(
                spent=75,
                campaign_remaining=275,
                gate_budget=75,
                gate_hard_limit=150,
                has_progress=True,
            ),
            150,
        )
        self.assertEqual(
            _LADDER.restored_gate_cap(
                spent=50,
                campaign_remaining=300,
                gate_budget=75,
                gate_hard_limit=150,
                has_progress=False,
            ),
            75,
        )

    def test_checkpoint_is_private_and_fingerprint_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CheckpointStore(Path(temporary))
            checkpoint = CampaignCheckpoint(
                run_id="test-run",
                lab_fingerprint="lab-a",
                mode="completion",
                progress_token="bearer-token",
            )
            path = store.save(checkpoint)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(
                store.load("test-run", expected_lab_fingerprint="lab-a").progress_token,
                "bearer-token",
            )
            with self.assertRaises(ValueError):
                store.load("test-run", expected_lab_fingerprint="lab-b")


if __name__ == "__main__":
    unittest.main()
