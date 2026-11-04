"""Remove bearer progression tokens from private Warden run artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = frozenset({"progress_token"})


def sanitize(value: Any) -> tuple[Any, int]:
    if isinstance(value, list):
        cleaned, removed = [], 0
        for item in value:
            result, count = sanitize(item)
            cleaned.append(result)
            removed += count
        return cleaned, removed
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        removed = 0
        for key, item in value.items():
            if key in SENSITIVE_KEYS:
                removed += 1
                continue
            result, count = sanitize(item)
            cleaned[key] = result
            removed += count
        return cleaned, removed
    return value, 0


def sanitize_file(path: Path, *, apply: bool) -> int:
    if path.suffix == ".jsonl":
        output: list[str] = []
        removed = 0
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                output.append(line)
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: {exc.msg}") from exc
            cleaned, count = sanitize(value)
            output.append(json.dumps(cleaned, ensure_ascii=False))
            removed += count
        if apply and removed:
            path.write_text("\n".join(output) + "\n")
        return removed
    try:
        value = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: {exc.msg}") from exc
    cleaned, removed = sanitize(value)
    if apply and removed:
        path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n")
    return removed


def sanitize_tree(root: Path, *, apply: bool) -> tuple[int, int]:
    files_changed = 0
    fields_removed = 0
    for path in sorted((*root.rglob("*.json"), *root.rglob("*.jsonl"))):
        removed = sanitize_file(path, apply=apply)
        if removed:
            files_changed += 1
            fields_removed += removed
    return files_changed, fields_removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="rewrite files; without this flag, report only")
    args = parser.parse_args()
    files, fields = sanitize_tree(args.root, apply=args.apply)
    action = "removed" if args.apply else "found"
    print(f"{action} {fields} sensitive fields in {files} files")
    return 1 if fields and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
