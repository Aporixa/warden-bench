# warden-bench

Warden Bench measures how adaptive attacks learn from a defended chat system and how those defenses change under repeated evaluation.

<img width="1376" height="768" alt="warden-8" src="https://github.com/user-attachments/assets/96897ae8-7db5-42b9-882b-4b28c7a7066d" />

The target is the Warden, an eight-gate lab built by Aporixa. Each gate guards a rotating password behind persona instructions, input moderation, output guards, and semantic checks. The public challenge is available at [warden.aporixa.com](https://warden.aporixa.com).

Warden Bench runs against an authorized local copy of the lab. Do not direct automated traffic at the hosted challenge. The [Warden terms](https://aporixa.com/terms#warden) prohibit that use.

## Run the progressive ladder

The ladder starts at gate 1, carries the signed progress token between gates, and stops when a gate holds. Every strategy at a gate shares one target-chat budget and one evidence state.

Prepare the operator environment once:

```bash
cd warden-bench/operator
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add `ANTHROPIC_API_KEY` to `operator/.env`.

Start the local lab in one terminal:

```bash
cd warden-bench
operator/ladder/local-lab.sh
```

The script reads the model configuration and OpenAI key from `../warden/backend/.env`. It replaces the passwords and certificate secret with temporary values. It also disables Slack notifications and corpus writes. On startup, it writes the generated targets to a private, gitignored `local-lab.env` file and writes a non-secret run fingerprint for checkpoint validation.

Start the ladder in another terminal:

```bash
cd warden-bench/operator
. .venv/bin/activate
python ladder/ladder.py \
  --lab-models ../../warden/backend/.env \
  --lab-repo ../../warden
```

The command prints its maximum target-chat cost and asks for confirmation before it spends. The default run is one outside-in completion campaign through level 7. It uses Claude Sonnet 5.5 as the attacker, evidence analyst, and extraction judge. PAIR drives the adaptive search and can invoke TAP or GAP through the shared hypothesis queue.

The ladder refuses a remote target unless you pass `--allow-remote`. Use that option only for another system that you own or have permission to test.

See the [ladder reference](operator/ladder/README.md) for budget controls, repeated runs, driver selection, and output fields.

## Choose a run mode

The default completion run uses reviewed, lab-independent technique cards from `operator/corpus/public/techniques.jsonl`. It does not read Warden source hints, earlier Warden observations, the cheatsheet, or the author oracle.

Run the current solvability control only with the explicit flag:

```bash
python ladder/ladder.py \
  --lab-models ../../warden/backend/.env \
  --lab-repo ../../warden \
  --author-oracle
```

No default or evaluation run selects the oracle. Oracle mode reads only the current, validated level 1 through 7 techniques in `operator/oracle/current.jsonl`. Add `--include-l8` to test the separate final gate.

Use `--evaluate` for independent knowledge-arm comparisons. Each arm starts at level 1 because each is a separate experiment.

| arm                | attacker knowledge                            | purpose                                                           |
| ------------------ | --------------------------------------------- | ----------------------------------------------------------------- |
| `cold`             | No seed corpus                                | Measures discovery from public gate metadata and target responses |
| `public-unadapted` | Reviewed upstream records                     | Public-library control; currently empty                           |
| `public-generated` | Local adaptations of public techniques        | Measures a warm external attacker                                 |
| `warden-observed`  | Public tiers plus earlier Warden observations | Measures transfer from prior campaigns                            |

Repeat `--arm` only in evaluation mode:

```bash
python ladder/ladder.py \
  --lab-models ../../warden/backend/.env \
  --lab-repo ../../warden \
  --evaluate \
  --arm cold \
  --arm warden-observed
```

## Understand the adaptive search

PAIR, TAP, and GAP share a `GateState` at each gate. The state retains response classes, semantic and explicit constraints, wrong candidates, and attempted technique families. Changing strategy does not restart progression or reacquire cleared gates.

The controller scores technique hypotheses using public relevance, transfer from the previous gate, observed progress, refusals, and cost. It suppresses dead hypotheses and gives more budget to partial leaks and guard blocks. The campaign has a 350-chat cap, a 75-chat soft limit per gate, and a 150-chat hard limit when the gate returns progress.

The hybrid evidence analyst sees only one attacker prompt and its target response. It accepts a semantic finding only when the model cites an exact substring from the response. The real submit endpoint must verify every candidate.

The ladder saves a private checkpoint after each strategy attempt. Resume an interrupted run with `--resume RUN_ID`. It rejects checkpoints from a different lab revision, model configuration, or password rotation.

The ten public technique cards are Aporixa-authored abstractions of reusable
families documented by current public tools. They are priors, not copied attack
payloads. The attacker model writes each exact attempt at runtime and adapts it
from the target's responses. The trace therefore records both the selected
hypothesis and the technique actually used by the generated attempt; those can
differ.

## Inspect run output

The ladder writes raw data under `operator/ladder/runs/<batch_id>/`. Git ignores this directory because responses can contain temporary secrets.

Each batch contains `batch.json` and one directory per campaign. A campaign directory contains:

- `manifest.json` with run mode, oracle-access status, models, code revision, budgets, capability profile, and source hashes
- `campaign.jsonl` with the versioned, append-only hypothesis and evidence trace
- `summary.json` with gate outcomes, costs, and accumulated evidence
- `probes.jsonl` with low-level driver diagnostics
- `seeds-used.jsonl` and, when applicable, `seeds-dropped.jsonl`

The campaign trace records strategy decisions, attempts, observations, extracted evidence, and verified outcomes. Read the [trace schema](operator/research/trace-schema.md) for the event definitions.

## Audit and publish research data

`operator/seeds.jsonl` is starting material, not the research dataset. Audit its provenance and duplication before using it in a publication:

```bash
cd warden-bench
operator/.venv/bin/python operator/corpus/audit.py operator/seeds.jsonl
```

The current legacy corpus contains 52 records. The audit reports missing creation dates, licenses, ancestry, and explicit knowledge tiers. Do not replace missing metadata with guesses.

Warden Bench classifies attempts across independent objective, strategy, representation, and interaction axes. The [technique classification reference](operator/research/taxonomy.md) defines version 1.

The release builder converts reviewed campaigns into an immutable temporal split. It excludes `author-oracle` by default, redacts exact secrets, records source hashes, and generates a dataset card. Follow the [dataset release guide](operator/corpus/release.md) before publishing a release.

Before sharing any raw run directory, remove progression bearer tokens:

```bash
operator/.venv/bin/python operator/corpus/sanitize_runs.py \
  operator/ladder/runs --apply
```

The release builder also removes progression-token fields as a defense in
depth. It does not make raw responses safe to publish: exact values and
structural disclosures still require human review. Never publish
`operator/ladder/checkpoints/`; checkpoints intentionally retain the live
progression token needed by `--resume` while a campaign remains resumable.
The ladder scrubs that credential after a campaign completes.

The [seed-library reference report](operator/research/2026-11-04-seed-library-reference-points.md) compares the legacy corpus with maintained Garak, PyRIT, DeepTeam, Promptfoo, and Mozilla 0DIN resources. The report uses those projects as reference points and does not import their payloads.

The [first outside-in completion note](operator/research/2026-11-04-first-outside-in-completion.md)
documents the 45-chat development campaign through gate 7 and separates public
technique priors, model-generated attempts, live target evidence, and oracle
access.

## Repository layout

```text
operator/campaign/   run modes, oracle boundary, and private checkpoints
operator/controller/ evidence-scored hypothesis scheduling
operator/core/       shared evidence analysis, campaign traces, and taxonomy
operator/ladder/     progressive runner, local-lab launcher, and run output
operator/corpus/     seed audit and reviewed dataset release tools
operator/oracle/     current target-specific solvability controls
operator/pair/       linear adaptive PAIR driver
operator/research/   schema references and research notes
operator/tap/        Tree of Attacks with Pruning driver
operator/gap/        Graph of Attacks with Pruning driver
operator/crescendo/  embedded-transcript escalation driver and experiments
operator/tests/      deterministic tests for evidence, provenance, and releases
browser-agent/       Playwright-based historical UI agent
manual/              human solves and notes
```

## Run the tests

Run the deterministic suite from the repository root:

```bash
operator/.venv/bin/python -m unittest discover -s operator/tests -v
```

The tests do not call the Warden or a model provider.

## Historical baseline

The committed probe logs predate the progressive ladder. Those experiments attacked individual gates, sometimes without progression enforcement, and used Claude Sonnet 4.6 as attacker and judge. Treat the following numbers as historical observations, not current benchmark results.

| Driver        | Search method                                   | Target chats or run count | Gates solved in the archived logs |
| ------------- | ----------------------------------------------- | ------------------------: | --------------------------------- |
| PAIR          | Linear attacker, judge, and feedback loop       |                 923 chats | 1, 2, 3, 4, 5, 7                  |
| TAP           | Tree search with top-width pruning              |                  87 chats | 1, 2, 3, 5, 7, and gate 6 once    |
| GAP           | Tree search with graph-wide strategy memory     |                 198 chats | 1, 2, 3, 4, 5, 7                  |
| Crescendo     | Benign-to-escalating transcript                 |                  34 chats | 1, 2                              |
| Browser agent | Claude driving the public UI through Playwright |          One full-lab run | 1                                 |
| Human         | Manual investigation                            |              Not measured | 6, 8                              |

In the archived runs, automation cleared gate 6 only after the human technique entered the shared seed corpus. No archived automated run cleared gate 8. The raw logs also show judge extraction failures and plausible but incorrect browser-agent guesses. These failures motivated verified outcomes, structured evidence, and an explicitly selected author-oracle control.

The historical hand-solve notes are in `manual/warden-cheatsheet.md`. Older probe files remain unchanged so later analysis can reproduce the original observations.

## Prior work and attribution

The current research model, campaign schema, taxonomy, provenance rules, and release process are Warden Bench work. The repository also contains implementations and adaptations of published attack methods:

- PAIR follows Chao et al., 2023, [_Jailbreaking Black Box Large Language Models in Twenty Queries_](https://arxiv.org/abs/2310.08419).
- TAP follows Mehrotra et al., 2023, [_Tree of Attacks: Jailbreaking Black-Box LLMs Automatically_](https://arxiv.org/abs/2312.02119).
- GAP follows Bagdasaryan et al., 2025, _Graph of Attacks with Pruning_.
- Crescendo follows Russinovich, Salem, and Eldan, 2024, [_Great, Now Write an Article About That_](https://arxiv.org/abs/2404.01833).
- `operator/parseltongue.py` adapts `parseltongue.ts` from [elder-plinius/G0DM0D3](https://github.com/elder-plinius/G0DM0D3).
- Earlier corpus and fingerprinting work drew from [DeepTeam](https://github.com/confident-ai/deepteam), [Garak](https://github.com/NVIDIA/garak), [PyRIT](https://github.com/Azure/PyRIT), OWASP guidance, L1B3RT4S, and G0DM0D3. File-level attribution remains in the relevant modules.

The lab format is in the tradition of Lakera's [Gandalf](https://gandalf.lakera.ai/). `operator/red-team-landscape.md` contains the longer historical reading list.

## Handle logs safely

Historical committed logs replace known lab passwords with `[REDACTED-L<gate>]`. That mechanical replacement also changed parts of some ordinary words. Structural disclosures such as acrostics and letter positions remain because they show how a defense leaked information.

New ladder traces contain raw local responses. Use temporary lab passwords, keep `operator/ladder/runs/` private, and complete publication review before creating a release.

Future diagnostic logs record only whether the server issued a progression
token. They do not record its value. Run the sanitizer above on data produced
by older revisions before copying or publishing it.

Enable the repository's commit guard once per clone:

```bash
git config core.hooksPath .githooks
```

The guard refuses staged ladder runs, checkpoints, environment files, browser
session state, private keys, and common provider-key formats.

Only test systems that you own or have permission to evaluate.
