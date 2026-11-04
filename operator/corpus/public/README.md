# Public technique corpus

This directory contains Warden-independent technique cards used by the default
completion operator. Cards describe reusable attack families and cite reviewed
public reference points. They are Aporixa-authored abstractions, not copied
upstream payloads.

`sources.jsonl` records upstream provenance, version, retrieval date, license,
and review status. `techniques.jsonl` records the local technique cards. Normal
runs may read this directory but must never read `operator/oracle/`.

Refresh source metadata monthly and before a published benchmark. Review and
test a new technique card before admitting it; do not append unreviewed prompts
directly to the legacy `operator/seeds.jsonl` file.

Validate the registry and card references from `warden-bench`:

```bash
operator/.venv/bin/python operator/corpus/public_cards.py \
  operator/corpus/public/sources.jsonl \
  operator/corpus/public/techniques.jsonl
```
