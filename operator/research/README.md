# Warden research records

Warden Bench records adaptive campaigns rather than treating successful prompts as the primary dataset. A campaign preserves what the attacker tried, what the target exposed, how the attacker changed strategy, and which defense revision produced the result.

The raw records are local research data. They can contain target responses, candidate secrets, and generated attack text. The ladder stores them under `operator/ladder/runs/`, which Git ignores. Review and sanitize a campaign before you publish it.

Older diagnostic logs can also contain a progression bearer token. Run
`operator/corpus/sanitize_runs.py` on the run tree before sharing it. Never
publish `operator/ladder/checkpoints/`, which intentionally retains that token
while a campaign remains resumable.

## Research artifacts

- `campaign.jsonl` is the versioned campaign trace. Use it for analysis and dataset construction.
- `manifest.json` identifies the knowledge arm, models, defense revision, capability profile, corpus hash, and campaign budget.
- `summary.json` contains derived campaign and gate statistics.
- `probes.jsonl` is a driver diagnostic log. Its event format is not a published dataset interface.
- `seeds.jsonl` contains starting material. Seeds are not findings and do not establish benchmark coverage.

See [the campaign trace schema](trace-schema.md) and
[the technique classification reference](taxonomy.md) for field definitions.
Run [the corpus audit](../corpus/README.md) before you construct a release.
Then follow [the dataset release guide](../corpus/release.md).

Current notes:

- [Seed-library reference points](2026-11-04-seed-library-reference-points.md)
- [First outside-in completion through gate 7](2026-11-04-first-outside-in-completion.md)

## Publication rule

Publish a finding only when the release identifies the supporting campaigns, defense revision, capability scope, knowledge arm, budget, and temporal cutoff. Keep author knowledge in the explicit `author-oracle` control. Do not merge author-oracle records into public or Warden-generated corpora.
