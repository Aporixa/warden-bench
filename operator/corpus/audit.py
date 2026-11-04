"""Audit seed provenance, duplication, and publication readiness."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

OPERATOR = Path(__file__).resolve().parents[1]
if str(OPERATOR) not in sys.path:
    sys.path.insert(0, str(OPERATOR))

from seedlib import classify_seed, load_seeds  # noqa: E402


def _normalized_prompt(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt).strip().casefold()


def audit_seeds(path: Path) -> dict[str, Any]:
    """Describe corpus quality without changing or rejecting the corpus."""

    seeds = load_seeds(path)
    tiers: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    prompt_groups: dict[str, list[int]] = defaultdict(list)
    issues: list[dict[str, Any]] = []

    for index, seed in enumerate(seeds, 1):
        try:
            tiers[classify_seed(seed).value] += 1
        except ValueError as exc:
            issues.append({"record": index, "code": "invalid-knowledge-tier", "detail": str(exc)})
        source = str(seed.get("source") or "")
        sources[source or "<missing>"] += 1
        if not source:
            issues.append({"record": index, "code": "missing-source"})
        if not seed.get("knowledge_tier"):
            issues.append({"record": index, "code": "inferred-knowledge-tier"})
        if not seed.get("created_at"):
            issues.append({"record": index, "code": "missing-created-at"})
        if not seed.get("license"):
            issues.append({"record": index, "code": "missing-license"})
        if not seed.get("ancestry"):
            issues.append({"record": index, "code": "missing-ancestry"})
        normalized = _normalized_prompt(str(seed.get("prompt") or ""))
        prompt_groups[normalized].append(index)

    duplicate_groups = [records for records in prompt_groups.values() if len(records) > 1]
    for records in duplicate_groups:
        issues.append({"records": records, "code": "duplicate-normalized-prompt"})

    return {
        "schema": "warden.corpus-audit",
        "schema_version": 1,
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "records": len(seeds),
        "knowledge_tiers": dict(sorted(tiers.items())),
        "sources": dict(sources.most_common()),
        "duplicate_groups": duplicate_groups,
        "issue_counts": dict(Counter(issue["code"] for issue in issues).most_common()),
        "issues": issues,
        "publication_ready": not issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?", default=OPERATOR / "seeds.jsonl")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="exit 1 when the audit finds an issue")
    args = parser.parse_args(argv)
    report = audit_seeds(args.path)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if args.strict and not report["publication_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
