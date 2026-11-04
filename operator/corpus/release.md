# Build a reviewed dataset release

The release builder converts complete campaign traces into a licensed dataset. It assigns whole campaigns to temporal splits and excludes `author-oracle` by default.

## Review campaigns

First remove progression bearer tokens from raw runtime artifacts created by
older Warden Bench revisions:

```bash
operator/.venv/bin/python operator/corpus/sanitize_runs.py \
  operator/ladder/runs --apply
```

Do not publish `operator/ladder/checkpoints/`. A resumable checkpoint retains
the live token required to continue its campaign. The release builder recursively removes any
`progress_token` field found in trace observations, but that safeguard does not
replace sanitizing and reviewing the complete raw run directory.

Inspect each raw `campaign.jsonl`. Record one decision per campaign in a JSON Lines file:

```json
{"campaign_id":"20261104T120000Z-cold-abc123","reviewer":"researcher@example.org","reviewed_at":"2026-11-05T15:00:00-05:00","allow_publish":true,"notes":"Checked raw text and provenance."}
```

Set `allow_publish` to `false` when a campaign contains material that must remain private. The builder excludes campaigns that have no review.

## Provide exact secrets

Create a local file with one exact secret per line. Do not commit this file. The builder also collects verified candidates from each trace.

Exact-value redaction cannot remove acrostics, letter positions, encodings, or other structural disclosures. Approve a campaign only after you inspect those disclosures.

## Build the release

Run this command from `warden-bench`:

```bash
operator/.venv/bin/python operator/corpus/release.py \
  operator/ladder/runs \
  --reviews operator/reviews.jsonl \
  --secret-file /path/to/local-secrets.txt \
  --output releases/warden-campaigns-2026.11 \
  --name warden-campaigns \
  --version 2026.11 \
  --license CC-BY-4.0 \
  --cutoff 2026-10-01T00:00:00Z
```

The output directory must not exist. The command writes:

- `observations.jsonl` with sanitized, classified observations
- `manifest.json` with source hashes, counts, license, and cutoff
- `exclusions.jsonl` with each omitted campaign and its reason
- `DATASET.md` with the release scope, review policy, and known limits

The builder requires observations on both sides of the cutoff. Use `--allow-empty-split` only for a private development release that will not support comparative claims.

Use `--author-oracle-only` to build a separate oracle release. The option excludes every other knowledge arm so oracle observations cannot enter a public-attacker release by accident.
