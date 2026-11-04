# First outside-in completion through gate 7

On 2026-11-04, Warden Bench completed gates 1 through 7 of a local Warden
instance in 45 target chats. This is a development result, not yet a benchmark
release. It came from one campaign and does not measure variance.

## Campaign boundary

- Mode: `completion`
- Knowledge arm: `public-current`
- Oracle accessed: `false`
- Starting corpus: 10 Aporixa-authored public technique cards
- Strategy: PAIR, with TAP and GAP available through the shared controller
- Driver that cleared each gate: PAIR
- Progression: enforced by the target; cleared gates were not restarted
- Scope: gates 1 through 7; gate 8 was excluded by design

The public cards cite Garak, PyRIT, DeepTeam, Promptfoo, and Mozilla 0DIN as
current reference points. They contain generic technique descriptions, not
upstream payloads or Warden values. No exact protected value from the campaign
appears in the public card corpus.

## Attribution

The controller allocated 13 of 45 target chats under a public
cross-language-transformation hypothesis. It allocated the other 32 under a
previous-gate-transfer hypothesis built from winning prompts observed earlier
in the same campaign.

That 13/32 split measures controller allocation, not exclusive causal credit.
All attacker calls had access to the ten public cards, and the attacker model
generated every exact attempt. Generated attempts could diverge from the
hypothesis label. Later code revisions record the selected hypothesis and the
classified winning technique separately to make that distinction auditable.

The defensible attribution is therefore:

- External sources supplied general technique priors through locally authored
  cards.
- The attacker model supplied all exact wording and runtime adaptations.
- The target supplied the evidence used to infer each candidate during the
  campaign.
- The target's submit endpoint verified every accepted candidate and issued
  progression.
- The author oracle and manual cheatsheet supplied none of this campaign's
  inputs.

It is not defensible to claim that a fixed percentage of the successful ideas
came from external sources from this one trace. A causal estimate requires
repeated cold, public-card, and ablation campaigns against fresh password
rotations.

## Publication status

The campaign predates fixes that stop a driver immediately after the semantic
analyst produces a verified candidate and that distinguish winning technique
from selected hypothesis in summaries. Treat it as evidence that the system can
complete the progression, not as the first row of a final comparison series.

Before any raw artifact is shared, remove progression bearer tokens with
`operator/corpus/sanitize_runs.py` and complete the human publication review.
Never publish ladder checkpoints.
