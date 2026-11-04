# Current red-team library reference points

> Document type: explanation. Research note, 2026-11-04.
> This note selects maintained public libraries that can measure Warden's seed
> coverage. It does not import their payloads. Recheck versions, source
> licenses, and dataset-specific terms before any future ingestion.

## Decision

Use Garak, PyRIT, DeepTeam, and Promptfoo as four independent reference points
for the Warden corpus. Add Mozilla 0DIN JEF and its threat-feed work as a
measurement reference. Compare metadata and technique coverage on a schedule;
do not merge upstream prompts into `seeds.jsonl`.

The comparison should answer four questions:

1. Which attack intents and transformations are absent from Warden?
2. Which target capabilities, such as stateful chat, tools, retrieval, files,
   images, or audio, does each attack require?
3. Which attempts remain effective across target model families and defense
   revisions?
4. Can another researcher reproduce the source, version, license decision,
   expected result, and observed result for each seed?

## Local baseline

The 2026-11-04 `seeds.jsonl` contains 52 records and 18 literal technique
labels. Two records are marked manual. The source counts are:

| Origin | Records | Share |
|---|---:|---:|
| Warden probe logs | 30 | 58% |
| Hand-written `deepteam-inspired` prompts | 12 | 23% |
| Hand-written `pliny-inspired` prompts | 8 | 15% |
| Manual records | 2 | 4% |

Nine records, 17% of the corpus, have fallback labels such as
`level-1-other`, `level-4-other`, or `level-8-other`. The largest named class
is `letter-association`, with seven records. The corpus is entirely textual.

These numbers were calculated directly from [`seeds.jsonl`](../seeds.jsonl).
The generator explains the structural weakness: it assigns classes with a
keyword heuristic, records a prompt and optional leak excerpt, and does not yet
mine confirmed chat/judge/submit chains from logs
([`build_seeds.py`](../build_seeds.py)). The `deepteam-inspired` entries are
local prompts patterned after a small selection of public techniques; they are
not a snapshot of DeepTeam's upstream attack registry
([`deepteam_extras.py`](../deepteam_extras.py)).

The current corpus therefore measures transfer among Warden-derived prompt
examples better than it measures coverage of current attack methods. Its
counts should not be described as coverage of DeepTeam, OWASP, Garak, or the
wider public attack corpus.

## Reference libraries

### 1. NVIDIA Garak

#### Why Garak is useful

Garak separates probes, detectors, generators, harnesses,
and evaluators. Its probe catalog includes static payload families and
transformations such as bad-character perturbations, encodings, prompt
injection, continuation, GCG, Goodside-style attacks, and leak replay. This is
a better reference taxonomy than Warden's prompt-word classifier because an
attack and its detector remain distinct. See the official
[Garak repository and probe catalog](https://github.com/NVIDIA/garak).

#### Freshness

Garak v0.17.0 was released on 2026-09-09. The preceding v0.16.0
introduced technique and intent annotations, intent-aware selection, probe
summaries, an adaptive-attack probe, and a changed report schema. These are
material changes after the older Garak-inspired Warden probes. See the official
[Garak releases](https://github.com/NVIDIA/garak/releases).

#### What to compare

Export only a manifest of probe id, technique tags,
intent tags, modality, primary detector, extended detectors, and upstream
version. Compare that manifest with Warden families. Pay special attention to
Unicode and invisible-character perturbations, adaptive probes, continuation,
indirect or web injection, and agent/tool attacks. Warden currently represents
none of these as first-class metadata.

#### License

Garak's source repository uses
[Apache License 2.0](https://github.com/NVIDIA/garak/blob/main/LICENSE). Record
the license of any separately downloaded resource as well as the code license.

### 2. Microsoft PyRIT dataset and technique registries

#### Why PyRIT is useful

PyRIT now models seeds, scenarios, attack techniques,
executors, converters, targets, scorers, and memory separately. Its typed seed
hierarchy can associate an objective with named adversarial prompts, conditions,
and scoring expectations. This provides a concrete reference for replacing
Warden's flat prompt records. See PyRIT's official
[framework architecture](https://github.com/microsoft/PyRIT/blob/main/doc/code/framework.md).

#### Freshness

PyRIT v1.0.0 was released on 2026-07-24 and v1.0.1 on
2026-07-30. The v1 release added typed, content-addressed identities,
capability-aware feedback for TAP and Crescendo, JSON-schema validation for
seed and scorer datasets, and loaders for Garak data, a local jailbreak
dataset, 0DIN Threat Feed, WildGuardMix, MM-SafetyBench, and XL-SafetyBench.
It also added or wired attack techniques including prompt decomposition,
word-game decomposition, Policy Puppetry, Garak Doctor, and GCG extension
protocols. See the official [PyRIT releases](https://github.com/microsoft/PyRIT/releases).

#### What to compare

Use PyRIT's provider catalog as an index, not as an
automatic download list. Capture dataset id, upstream revision, objective,
harm or intent categories, media types, expected result, scorer type, license,
and whether access is gated. Its own configuration guide warns that full
dataset preload may require network access, credentials, or acceptance of
dataset licenses
([PyRIT configuration](https://github.com/microsoft/PyRIT/blob/main/doc/getting_started/pyrit_conf.md)).

#### License

PyRIT code is
[MIT licensed](https://github.com/microsoft/PyRIT/blob/main/LICENSE), but the
datasets it loads retain their own terms. A PyRIT loader is not evidence that
the underlying examples may be copied into Warden.

### 3. DeepTeam

#### Why DeepTeam is useful

DeepTeam is primarily a dynamic attack generator rather
than a static prompt dump. Its current catalog describes more than 20
single-turn and multi-turn attack methods and more than 50 vulnerability
classes, including prompt leakage and agent-specific goal, tool, identity,
indirect-instruction, and inter-agent failures. See the official
[DeepTeam repository](https://github.com/confident-ai/deepteam).

#### Freshness

DeepTeam 1.0.10 was published on 2026-10-16, after the local
`deepteam-inspired` list was written. The published package history records
six releases during 2026 through October
([DeepTeam on PyPI](https://pypi.org/project/deepteam/)). The current project
generates adversarial cases at runtime and combines attacks with vulnerability
classes, so twelve static local approximations are not a meaningful coverage
claim.

#### What to compare

Snapshot class names and documented compatibility from
the installed, pinned release. Record whether an attack is single-turn,
multi-turn, agent-specific, encoding-based, or model-generated. Compare the
result with Warden's technique registry. Treat documentation and the installed
package as separate evidence because a 2026 issue documented attacks present
on `main` but missing from a tagged package
([DeepTeam issue 197](https://github.com/confident-ai/deepteam/issues/197)).

#### License

DeepTeam uses
[Apache License 2.0](https://github.com/confident-ai/deepteam/blob/main/LICENSE.md).
Generated cases should still carry the generator version, model, prompt
configuration, and generation date rather than being attributed as upstream
static seeds.

### 4. Promptfoo red-team plugins and strategies

#### Why Promptfoo is useful

Promptfoo distinguishes a plugin that generates tests
for a vulnerability from a strategy that transforms or orchestrates those
tests. Its current documentation lists 157 plugins in six categories. Its
strategy registry includes single-turn and multi-turn methods, plugin-specific
targeting, and a retry strategy that turns prior failures into regression
cases. See the official [plugin catalog](https://www.promptfoo.dev/docs/red-team/plugins/)
and [strategy catalog](https://www.promptfoo.dev/docs/red-team/strategies/).

#### Freshness

Promptfoo 0.123.0 was released on 2026-09-10, and its 2026
release notes include adaptive agentic multi-turn strategies, authoritative
markup injection, wordplay tests, and `jailbreak:meta`, a multi-agent attack
generator. See the official [Promptfoo releases](https://github.com/promptfoo/promptfoo/releases)
and [release notes](https://www.promptfoo.dev/docs/releases/).

#### What to compare

Record plugin id separately from strategy id. A Warden
record needs both the tested objective and the transformation or orchestration
used to test it. Compare Promptfoo's indirect injection, tool and agent,
markup, multilingual, obfuscation, and multi-turn coverage with Warden. Do not
count 157 plugins as 157 reusable prompt seeds; many are generated tests for
application risks outside the guarded-secret lab.

#### License

Promptfoo's repository is
[MIT licensed](https://github.com/promptfoo/promptfoo/blob/main/LICENSE).
Hosted generation is a separate operational concern, so any future comparison
runner should default to local manifests and explicitly configured providers.

### 5. Mozilla 0DIN JEF and threat intelligence

#### Why 0DIN is useful

0DIN JEF is a scoring reference rather than a seed
library. It scores jailbreak tactics on model impact radius, retargetability,
and output fidelity. Version 0.8.2, released 2026-08-24, also made several
scorers refusal-aware. See the official
[0DIN JEF repository](https://github.com/0din-ai/0din-JEF) and
[release history](https://github.com/0din-ai/0din-JEF/releases).

0DIN also maintains a prompt toolkit with similarity signatures, a jailbreak
classifier, and threat-feed integration
([0DIN prompt toolkit](https://github.com/0din-ai/prompt-toolkit)). This is a
useful reference for deduplication and freshness checks without copying threat
feed contents.

#### What to compare

Add model/vendor breadth, retargetability across guarded
secret shapes, and output fidelity to Warden's aggregate reporting. Store
upstream identifiers and hashes for any authorized threat-feed comparison.
Do not treat a feed match as permission to redistribute the matched material.

## Coverage gaps to track

The upstream comparison yields the following initial gap register. This is a
manifest-level assessment, not a claim that every missing family can solve the
Warden.

| Gap in Warden metadata or attempts | Strongest reference |
|---|---|
| Intent separate from attack technique | Garak 0.16+ |
| Objective, conditions, and scoring expectation | PyRIT typed seeds |
| Target capability requirements | PyRIT target capabilities |
| Dynamic attack generation with recorded generator identity | DeepTeam |
| Vulnerability plugin separate from attack strategy | Promptfoo |
| Failed-attempt regression as a named strategy | Promptfoo `retry` |
| Unicode, invisible-character, and bad-character perturbations | Garak |
| Decomposition and word-game attack methods | PyRIT v1 |
| Agent tools, identity, indirect instructions, and inter-agent attacks | DeepTeam / Promptfoo |
| Stateful multi-turn compatibility | PyRIT / DeepTeam / Promptfoo |
| Image, audio, file, and document inputs | PyRIT / Promptfoo |
| Cross-model impact, retargetability, and output fidelity | 0DIN JEF |
| Similarity-based deduplication and threat-feed freshness | 0DIN prompt toolkit |

For the present stateless, text-only Warden endpoint, capability metadata is
essential. It lets the corpus mark multi-turn, tool, retrieval, and multimodal
methods as inapplicable instead of silently treating them as failed attacks.

## Proposed comparison record

Keep upstream reference manifests outside `seeds.jsonl`. A comparison record
should contain at least:

```json
{
  "reference_id": "upstream-project:stable-id",
  "reference_version": "tag-or-commit",
  "retrieved_at": "2026-11-04T00:00:00Z",
  "source_url": "https://...",
  "license": "SPDX-or-review-required",
  "intent": ["secret-extraction"],
  "technique": ["transformation-family"],
  "orchestration": "single-turn",
  "required_capabilities": ["text"],
  "modalities": ["text"],
  "expected_signal": ["candidate-secret", "guard-block"],
  "local_coverage": "covered|partial|missing|inapplicable",
  "local_seed_ids": [],
  "notes": "No upstream payload copied."
}
```

This record must not contain a raw upstream payload unless a later license and
research-data review explicitly approves ingestion.

## Refresh policy

1. Pin one stable version or commit per reference project.
2. Refresh manifests monthly and before a published Warden benchmark run.
3. Review release notes for new attack, intent, modality, scorer, and schema
   entries.
4. Produce a machine-readable coverage diff and a short human review.
5. Add a local attack family only after defining its expected signal and
   required target capabilities.
6. Keep `public-unadapted`, `public-generated`, `warden-observed`, and
   `author-oracle` provenance tiers separate in evaluation.
7. Run leave-one-family-out and time-split evaluations so the adaptive attacker
   cannot score well only by replaying techniques already seen in Warden logs.

The immediate goal is not a larger prompt count. It is a current, reproducible
account of which public attack methods Warden can exercise, which it cannot,
and which defenses each result actually tests.
