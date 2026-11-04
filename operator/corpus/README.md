# Audit a Warden corpus

Use the corpus audit to expose provenance and duplication problems before you use seeds in a benchmark or publish a dataset.

Run the audit from `warden-bench`:

```bash
operator/.venv/bin/python operator/corpus/audit.py operator/seeds.jsonl
```

Add `--strict` in continuous integration. The command exits with status `1` when it finds an issue:

```bash
operator/.venv/bin/python operator/corpus/audit.py operator/seeds.jsonl --strict
```

The audit reports:

- Record counts by knowledge tier and source
- Exact duplicates after case and whitespace normalization
- Missing source, creation date, license, and ancestry fields
- Knowledge tiers that the loader inferred from legacy source names
- A SHA-256 digest of the audited file

The audit does not modify `seeds.jsonl`. A failed legacy audit is expected until each retained seed has reviewed provenance. Do not fill missing fields with guessed values. Quarantine a seed when its origin or license cannot be established.

After you collect campaign traces, use the
[dataset release guide](release.md) to build a reviewed temporal split.
Before sharing raw run artifacts, use `sanitize_runs.py` as described in that
guide to remove progression bearer tokens written by older revisions.
