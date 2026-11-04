# Run the progression operator

The ladder runs one authorized outside-in campaign against a local Warden lab.
It starts at gate 1, carries the signed progress token, and stops after gate 7
by default. Gate 8 requires `--include-l8` because it uses a different model,
reasoning configuration, and defense profile.

The default command does not load Warden source hints, prior Warden attempts,
the manual cheatsheet, or the author oracle. It uses public, lab-independent
technique cards and evidence that the target returns during the current run.

## Start the local lab

Run the launcher from the `warden-bench` directory:

```bash
operator/ladder/local-lab.sh
```

The launcher reads model settings and the OpenAI key from
`../warden/backend/.env`. It overrides passwords, the certificate secret,
Slack settings, and corpus logging for the local process.

The launcher writes two gitignored files:

- `operator/ladder/runs/local-lab.env` contains the generated local passwords.
  The file has mode `0600`. Use it only to diagnose the local test process.
- `operator/ladder/runs/local-lab.json` contains a lab-run ID and a password
  fingerprint. The ladder records this data and rejects checkpoints from a
  different password rotation.

Restart the local lab to apply launcher changes made after a process started.

## Run a completion campaign

Prepare the operator environment, then run the existing command:

```bash
cd operator
. .venv/bin/activate
python ladder/ladder.py \
  --lab-models ../../warden/backend/.env \
  --lab-repo ../../warden
```

The default campaign has these settings:

- mode: `completion`
- gates: 1 through 7
- corpus: `corpus/public/techniques.jsonl`
- controller: evidence-scored hypothesis queue
- strategies: PAIR, TAP, then GAP
- campaign budget: 350 target chats
- gate soft limit: 75 target chats
- gate hard limit after observable progress: 150 target chats
- semantic evidence analyst: enabled

The command prints the maximum target-chat cost and asks for confirmation.
Pass `--yes` to skip the confirmation.

## Understand strategy selection

PAIR is the primary adaptive strategy. Each public technique card becomes a
hypothesis. The controller scores each hypothesis using its public prior,
transfer from the previous gate, observed engagement, partial leakage, guard
blocks, rejected candidates, refusals, and estimated cost.

The controller suppresses a hypothesis after three comparable refusals or five
unproductive observations. A partial leak or guard block keeps the hypothesis
active and can extend the gate from the soft limit to the hard limit.

TAP and GAP are tools in the same hypothesis queue. TAP supplies breadth. GAP
uses graph memory to refine a promising line. All strategies share one
`GateState`, one target-chat budget, one progress token, and one run log.

Use `--chain` to restrict the available strategies for an evaluation:

```bash
python ladder/ladder.py ... --chain pair
python ladder/ladder.py ... --chain pair,tap
python ladder/ladder.py ... --chain pair,tap,gap,crescendo
```

Crescendo embeds the transcript in each request because the target endpoint is
stateless. The gate-8 research scripts under `crescendo/` are not ladder
strategies because some contain target-specific knowledge.

## Understand semantic evidence analysis

The deterministic extractor records explicit lengths, positions, prefixes,
and similar constraints. The semantic analyst runs only on engaged responses
and unsupported candidates.

The analyst receives only the attacker prompt and target response. It must cite
an exact substring from the response for every finding. The ladder discards
ungrounded findings. A candidate from the analyst counts only after the real
`/api/submit` endpoint verifies it.

Disable the analyst for an ablation run:

```bash
python ladder/ladder.py ... --no-semantic-analyst
```

## Resume an interrupted campaign

The ladder saves a private checkpoint after each strategy attempt. The
checkpoint contains the progress token, current gate, complete observable
evidence, hypothesis history, spend, and prior winning prompts.

The progress token is a bearer credential for the current local lab process.
Keep `operator/ladder/checkpoints/` private and never include it in a dataset,
release archive, issue, or commit. A resumable campaign retains the token; the
ladder scrubs it from the checkpoint after the campaign completes.

Resume the campaign explicitly:

```bash
python ladder/ladder.py \
  --lab-models ../../warden/backend/.env \
  --lab-repo ../../warden \
  --resume RUN_ID
```

The ladder rejects the checkpoint if the lab URL, source revision, model
configuration, lab-run ID, or password fingerprint changed. The ladder never
resumes a checkpoint automatically.

## Run the author oracle

No automated run selects the author oracle. Start the solvability control with
the explicit flag:

```bash
python ladder/ladder.py \
  --lab-models ../../warden/backend/.env \
  --lab-repo ../../warden \
  --author-oracle
```

Oracle mode reads only `operator/oracle/current.jsonl`. That file contains the
current, validated L1 through L7 techniques from the current section of
`manual/warden-cheatsheet.md`. It excludes historical April techniques.

The corpus access guard fails closed if completion or evaluation mode resolves
a path under `operator/oracle/`. The manifest records `oracle_accessed` for
every campaign. Exclude oracle campaigns from outside-in completion rates.

Add `--include-l8` to run the separate final-gate control.

## Run comparative evaluations

Use `--evaluate` to start fresh campaigns for knowledge-arm comparisons:

```bash
python ladder/ladder.py ... --evaluate --arm cold --arm public-generated
```

Evaluation mode resets progression for every arm. This reset is intentional
because each arm is an independent experiment. Default completion mode does
not reset when PAIR, TAP, or GAP changes at the current gate.

Available evaluation arms are:

| Arm | Knowledge |
|---|---|
| `cold` | Public gate metadata and current target responses only |
| `public-unadapted` | Reviewed upstream records, currently empty |
| `public-generated` | Legacy local adaptations of public methods |
| `warden-observed` | Public tiers plus prior Warden observations |

The target-specific oracle is not an evaluation arm. Use `--author-oracle`.

## Inspect campaign output

The ladder writes private data under `operator/ladder/runs/<batch_id>/`.
Responses can contain temporary secrets, so Git ignores the directory.

Each campaign directory contains:

- `manifest.json` with the run mode, oracle-access status, source hashes,
  models, lab fingerprint, budgets, and target capabilities
- `campaign.jsonl` with ordered hypothesis scores, prompts, observations,
  evidence, pivots, progression events, and outcomes
- `probes.jsonl` with driver, judge, chat, and submit diagnostics
- `summary.json` with per-gate results and cost
- `seeds-used.jsonl` with the exact corpus records available to the campaign

Private checkpoints are under `operator/ladder/checkpoints/`. Git ignores both
runtime directories.

Current diagnostic logs store `progress_token_issued` as a boolean and do not
store the token value. Sanitize artifacts written by older revisions before
sharing them:

```bash
operator/.venv/bin/python operator/corpus/sanitize_runs.py \
  operator/ladder/runs --apply
```

Run the same command without `--apply` as a publication check. A clean tree
reports zero sensitive fields.

## Run deterministic tests

Run the suite from the `warden-bench` directory:

```bash
operator/.venv/bin/python -m unittest discover -s operator/tests -v
```

The tests do not call a target or model provider. They cover oracle isolation,
private checkpoints, evidence serialization, hypothesis suppression, semantic
grounding, trace resumption, provenance, taxonomy, and release redaction.

Only test systems that you own or have permission to evaluate. Do not direct
automated traffic at the hosted Warden challenge.
