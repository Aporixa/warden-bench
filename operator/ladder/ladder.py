"""Ladder: automated attempts up the Warden's full gate sequence.

Earlier bench runs attacked one gate at a time against a lab with progress
enforcement off. This runner climbs the ladder the way a player has to:
gate 1 first, and each later gate only after the previous one is cleared.
The lab's signed progress_token is carried forward. A run stops at the
first gate that holds, and that gate is the result.

Escalation chain: at each gate the drivers run in order (default PAIR, TAP,
then GAP). An evidence-scored hypothesis queue chooses the next strategy.
All strategies draw from one target-chat budget. The controller suppresses
dead hypotheses and extends a gate only when it observes progress.

The default is one outside-in completion campaign through gate 7 using the
reviewed public technique corpus. Independent knowledge arms are available
only with --evaluate. The target-specific oracle is available only with the
explicit --author-oracle flag.

Every arm keeps structured run evidence and carries verified techniques to
later gates.

--repeat N runs N ladders per arm (arms interleaved) and writes a combined
batch.json.

    python ladder/ladder.py --lab-models ../../warden/backend/.env --lab-repo ../../warden --repeat 3
    python ladder/ladder.py --evaluate --arm public --chain tap
    python ladder/ladder.py --author-oracle                 # explicit solvability control
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import statistics
import subprocess
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
OPERATOR = HERE.parent
RUNS = HERE / "runs"
MAX_LEVEL = 8
DEFAULT_MAX_LEVEL = 7
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
DRIVERS = ("pair", "tap", "gap", "crescendo")
DEFAULT_CHAIN = ("pair", "tap", "gap")
ARM_ALIASES = {"public": "public-generated"}
ARMS = (
    "cold",
    "public-unadapted",
    "public-generated",
    "warden-observed",
    *ARM_ALIASES,
)
# The gate-8 instruments in crescendo/ (bleed, trigger, calibrate,
# blind_search, adaptive, solve_l8, level_contrast) are deliberately not
# drivers here: they were built while hand-solving gate 8, and some read the
# real gate-8 system prompt. They measure the author's solve, not an attacker.

# Only these names are read from --lab-models, so it is safe to point it at
# the lab's own .env: secrets in that file are never read or recorded.
_LAB_MODEL_KEY = re.compile(
    r"^(LAB_MODEL|LAB_REASONING|MODEL_[1-8]|REASONING_[1-8]|LEAK_JUDGE_MODEL|LEAK_JUDGE_REASONING)$")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def read_lab_models(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if not m or not _LAB_MODEL_KEY.match(m.group(1)):
            continue
        val = m.group(2).split(" #")[0].strip().strip("\"'")
        out[m.group(1)] = val
    return out


def target_model_for(level: int, lab_models: dict[str, str]) -> dict[str, str | None]:
    # Mirrors warden/backend/app/levels.py: MODEL_n falls back to LAB_MODEL.
    return {"model": lab_models.get(f"MODEL_{level}") or lab_models.get("LAB_MODEL"),
            "reasoning": lab_models.get(f"REASONING_{level}") or lab_models.get("LAB_REASONING")}


def git_rev(repo: Path | None) -> str | None:
    if not repo:
        return None
    try:
        rev = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True,
                               text=True, check=True).stdout.strip()
        return rev + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_chain(text: str) -> list[str]:
    chain = [d.strip().lower() for d in text.split(",") if d.strip()]
    bad = [d for d in chain if d not in DRIVERS]
    if not chain or bad or len(set(chain)) != len(chain):
        raise argparse.ArgumentTypeError(
            f"--chain takes a comma list of distinct drivers from {', '.join(DRIVERS)}")
    return chain


def restored_gate_cap(*, spent: int, campaign_remaining: int,
                      gate_budget: int, gate_hard_limit: int,
                      has_progress: bool) -> int:
    """Restore the hard gate allowance when saved evidence earned it."""

    limit = gate_hard_limit if has_progress else gate_budget
    return min(limit, spent + campaign_remaining)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm", action="append", choices=ARMS,
                   help="repeatable evaluation knowledge tier; requires --evaluate")
    p.add_argument("--evaluate", action="store_true",
                   help="run independent knowledge-arm campaigns instead of completion mode")
    p.add_argument("--author-oracle", action="store_true",
                   help="explicit target-specific solvability control; never selected automatically")
    p.add_argument("--include-l8", action="store_true",
                   help="include the materially different final gate (default stops after gate 7)")
    p.add_argument("--resume", metavar="RUN_ID",
                   help="resume an interrupted completion campaign from its private checkpoint")
    p.add_argument("--base", default=os.environ.get("WARDEN_BASE", "http://127.0.0.1:8000"))
    p.add_argument("--attacker-model", default="claude-sonnet-5-5",
                   help="attacker and judge for every driver (default: claude-sonnet-5-5)")
    p.add_argument("--no-semantic-analyst", action="store_true",
                   help="disable quote-grounded semantic evidence extraction")
    p.add_argument("--chain", type=parse_chain, default=list(DEFAULT_CHAIN),
                   help="strategy order per gate (default: pair,tap,gap)")
    p.add_argument("--gate-budget", type=int, default=75,
                   help="soft target-chat budget per gate (default 75)")
    p.add_argument("--gate-hard-limit", type=int, default=150,
                   help="hard gate cap available after observable progress (default 150)")
    p.add_argument("--campaign-budget", type=int, default=350,
                   help="target-chat cap across the entire campaign (default 350)")
    p.add_argument("--repeat", type=int, default=1, help="ladders per arm (default 1)")
    p.add_argument("--branch", type=int, default=3, help="TAP/GAP branching factor")
    p.add_argument("--width", type=int, default=2, help="TAP/GAP survivors per layer")
    p.add_argument("--depth", type=int, default=3, help="TAP/GAP layers")
    p.add_argument("--turns", type=int, default=5, help="Crescendo turns per arc")
    p.add_argument("--pair-turns", type=int, default=5, help="target calls per PAIR refinement attempt")
    p.add_argument("--max-level", type=int, help=argparse.SUPPRESS)
    p.add_argument("--lab-models", type=Path, help="file with MODEL_n / REASONING_n lines (only those are read)")
    p.add_argument("--lab-repo", type=Path, help="lab checkout, to record its git revision")
    p.add_argument("--lab-run-manifest", type=Path, default=HERE / "runs" / "local-lab.json",
                   help="local-lab run identity manifest (default: ladder/runs/local-lab.json)")
    p.add_argument("--allow-unenforced", action="store_true",
                   help="run even if the lab does not enforce progression (CERT_SECRET unset)")
    p.add_argument("--allow-remote", action="store_true",
                   help="target a non-local lab you operate. Never the hosted Warden.")
    p.add_argument("--yes", action="store_true", help="skip the spend confirmation")
    args = p.parse_args(argv)
    if args.evaluate and args.author_oracle:
        p.error("--evaluate and --author-oracle are mutually exclusive")
    if args.arm and not args.evaluate:
        p.error("--arm is available only with --evaluate")
    if args.resume and (args.evaluate or args.author_oracle or args.repeat != 1):
        p.error("--resume is available only for one default completion campaign")
    args.max_level = args.max_level or (MAX_LEVEL if args.include_l8 else DEFAULT_MAX_LEVEL)
    if args.max_level == MAX_LEVEL and not args.include_l8:
        p.error("gate 8 requires --include-l8")
    if not 1 <= args.max_level <= MAX_LEVEL:
        p.error("--max-level must be between 1 and 8")
    positive = (args.repeat, args.gate_budget, args.gate_hard_limit,
                args.campaign_budget, args.pair_turns)
    if any(value < 1 for value in positive):
        p.error("budgets, attempts, repeats, and turns must be at least 1")
    if args.gate_hard_limit < args.gate_budget:
        p.error("--gate-hard-limit cannot be smaller than --gate-budget")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sys.path.insert(0, str(OPERATOR))
    sys.path.insert(0, str(HERE))
    from campaign import (CampaignCheckpoint, CheckpointStore, RunMode,  # noqa: E402
                          lab_fingerprint, resolve_run_mode,
                          validate_corpus_access)

    mode = resolve_run_mode(evaluate=args.evaluate, author_oracle=args.author_oracle)
    if mode == RunMode.COMPLETION:
        arms = ["public-current"]
        seed_path = OPERATOR / "corpus" / "public" / "techniques.jsonl"
    elif mode == RunMode.AUTHOR_ORACLE:
        arms = ["author-oracle"]
        seed_path = OPERATOR / "oracle" / "current.jsonl"
    else:
        requested_arms = args.arm or ["cold", "public-generated"]
        arms = list(dict.fromkeys(ARM_ALIASES.get(arm, arm) for arm in requested_arms))
        seed_path = OPERATOR / "seeds.jsonl"
    seed_path = validate_corpus_access(mode, seed_path, operator_root=OPERATOR)
    host = urlparse(args.base).hostname or ""
    if host not in LOCAL_HOSTS and not args.allow_remote:
        print(f"refusing {args.base}: the ladder runs against a local lab. The hosted Warden's terms "
              "do not allow automated traffic.", file=sys.stderr)
        return 2

    os.environ["WARDEN_BASE"] = args.base   # the drivers read it at import
    os.environ["WARDEN_SEEDS_PATH"] = str(seed_path)
    import tap.tap as T                     # noqa: E402
    import gap.gap as G                     # noqa: E402
    import crescendo.crescendo as C         # noqa: E402
    import pair.pair as P                    # noqa: E402
    from core import (ANALYST_SYSTEM, CampaignTrace, GateState,  # noqa: E402
                      HybridEvidenceAnalyst,
                      classify_technique, observation_payload,
                      validate_trace)
    from controller import Hypothesis, HypothesisScheduler  # noqa: E402
    from public import (PUBLIC_ATTACKER_SYSTEM, PUBLIC_CRESCENDO_SYSTEM,  # noqa: E402
                        PUBLIC_GAP_SYSTEM, public_brief_fields,
                        public_seeds)
    from seedlib import (KnowledgeTier, classify_seed,  # noqa: E402
                         seeds_through_tier)

    if T._attacker is None:
        print("ANTHROPIC_API_KEY not set (operator/.env) or anthropic SDK missing", file=sys.stderr)
        return 1

    def analyst_model_call(body: str) -> str:
        response = T._attacker.messages.create(
            model=args.attacker_model,
            max_tokens=1200,
            system=[{"type": "text", "text": ANALYST_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": body}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()

    evidence_analyst = HybridEvidenceAnalyst(
        None if args.no_semantic_analyst else analyst_model_call
    )
    T.observe_attempt = G.observe_attempt = C.observe_attempt = P.observe_attempt = evidence_analyst.observe

    per_tree = args.branch + (args.depth - 1) * args.width * args.branch
    worst_case = {"pair": args.pair_turns, "tap": per_tree,
                  "gap": per_tree, "crescendo": args.turns}
    too_big = [d for d in args.chain if worst_case[d] > args.gate_hard_limit]
    if too_big:
        print(f"--gate-hard-limit {args.gate_hard_limit} is smaller than one attempt of {', '.join(too_big)} "
              f"({', '.join(f'{d}={worst_case[d]}' for d in too_big)})", file=sys.stderr)
        return 2

    lab_models = read_lab_models(args.lab_models) if args.lab_models else {}
    lab_revision = git_rev(args.lab_repo)
    lab_run = {}
    if args.lab_run_manifest.exists():
        try:
            lab_run = json.loads(args.lab_run_manifest.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"invalid --lab-run-manifest: {exc}", file=sys.stderr)
            return 2
    try:
        health = T.client.get("/healthz").json()
        meta = T.client.get("/api/levels").json()
        enforced = bool(T.client.post("/api/progress", json={}).json().get("enforced"))
    except Exception as e:
        print(f"lab not reachable at {args.base}: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not enforced and not args.allow_unenforced:
        print("the lab does not enforce progression (CERT_SECRET unset). Set a throwaway CERT_SECRET "
              "in the local lab so the ladder matches production, or pass --allow-unenforced.",
              file=sys.stderr)
        return 2

    worst = args.campaign_budget * len(arms) * args.repeat
    active_lab_fingerprint = lab_fingerprint(
        base=args.base,
        revision=lab_revision,
        models=lab_models,
        lab_run_id=lab_run.get("lab_run_id"),
        password_fingerprint=lab_run.get("password_fingerprint"),
    )
    checkpoint_store = CheckpointStore(HERE / "checkpoints")
    resume_checkpoint = None
    if args.resume:
        try:
            resume_checkpoint = checkpoint_store.load(
                args.resume,
                expected_lab_fingerprint=active_lab_fingerprint,
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"cannot resume {args.resume}: {exc}", file=sys.stderr)
            return 2
        if resume_checkpoint.mode != RunMode.COMPLETION.value:
            print("only completion checkpoints may resume", file=sys.stderr)
            return 2

    print(f"lab        {args.base}  progression enforced={enforced}  rev={lab_revision}")
    print(f"models     {args.attacker_model} (attacker, judge, and semantic analyst)")
    print(f"mode       {mode.value}" + ("  *** TARGET-SPECIFIC ORACLE ***" if args.author_oracle else ""))
    print(f"arms       {', '.join(arms)}  x {args.repeat} campaign(s) each")
    print(f"chain      {' -> '.join(args.chain)}  (PAIR {args.pair_turns} turns; TAP/GAP "
          f"b={args.branch} w={args.width} d={args.depth}; Crescendo {args.turns} turns)")
    print(f"budget     {args.campaign_budget} chats per campaign; gate soft/hard "
          f"{args.gate_budget}/{args.gate_hard_limit}; at most {worst}, plus attacker/judge calls")
    if not lab_models:
        print("note       no --lab-models: target models will not be recorded in the manifest")
    if not args.yes and input("spend? [y/N] ").strip().lower() != "y":
        return 0

    loaded_seeds = list(T._SEEDS)
    unadapted_seeds, unadapted_dropped = public_seeds(
        loaded_seeds,
        allowed_tiers={KnowledgeTier.PUBLIC_UNADAPTED},
    )
    generated_seeds, generated_dropped = public_seeds(loaded_seeds)
    observed_seeds = seeds_through_tier(
        loaded_seeds, KnowledgeTier.WARDEN_OBSERVED)
    arm_seeds = {
        "public-current": loaded_seeds,
        "cold": [],
        "public-unadapted": unadapted_seeds,
        "public-generated": generated_seeds,
        "warden-observed": observed_seeds,
        "author-oracle": loaded_seeds,
    }
    arm_dropped = {
        "cold": [{"technique": s.get("technique"), "source": s.get("source"),
                  "reason": "cold arm uses no seeds"} for s in loaded_seeds],
        "public-unadapted": unadapted_dropped,
        "public-generated": generated_dropped,
    }
    orig_select = T._select_seeds_for
    public_system = {"tap": PUBLIC_ATTACKER_SYSTEM, "gap": PUBLIC_GAP_SYSTEM,
                     "crescendo": PUBLIC_CRESCENDO_SYSTEM}

    # GAP and Crescendo carry their own chat/submit/judge/log copies that do
    # not send the progress token. Point them at TAP's, so every driver uses
    # one lab client, one token, one judge and one log per run.
    for M in (G, C):
        M.chat, M.submit, M.judge_extract, M._log = T.chat, T.submit, T.judge_extract, T._log
        M._attacker = T._attacker
        M.TARGET_SLEEP_S = T.TARGET_SLEEP_S

    if resume_checkpoint:
        matches = list(RUNS.glob(f"*/{resume_checkpoint.run_id}"))
        if len(matches) != 1:
            print(f"cannot locate one run directory for {resume_checkpoint.run_id}", file=sys.stderr)
            return 2
        batch_dir = matches[0].parent
        batch_id = batch_dir.name
    else:
        batch_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-batch-{secrets.token_hex(3)}"
        batch_dir = RUNS / batch_id
        batch_dir.mkdir(parents=True)
    results: list[dict[str, Any]] = []

    def configure_arm(arm: str, memory: list[dict[str, Any]]) -> None:
        T.ATTACKER_MODEL = G.ATTACKER_MODEL = C.ATTACKER_MODEL = args.attacker_model
        T.PROGRESS_TOKEN = None
        T._SEEDS = arm_seeds[arm]
        systems = public_system
        T._TAP_ATTACKER_SYSTEM = systems["tap"]
        G._GAP_ATTACKER_SYSTEM = systems["gap"]
        C._CRESCENDO_ATTACKER_SYSTEM = systems["crescendo"]

        def select(level: int, cap: int, _base=orig_select, _mem=memory) -> list[dict[str, Any]]:
            # Run memory first: what cleared earlier gates in this run. The
            # base selector reads T._SEEDS, which is the arm's seed set.
            mem = _mem[:cap]
            return mem + _base(level, cap - len(mem))
        T._select_seeds_for = G._select_seeds_for = C._select_seeds_for = select

    def run_driver(driver: str, level: int, brief: Any,
                   focus: str,
                   state: GateState) -> dict[str, Any]:
        """One attempt by one driver. Returns status, chats, and the prompt
        that cleared the gate (if any)."""
        if driver == "pair":
            r = P.run_pair(
                level,
                replace(brief),
                turns=args.pair_turns,
                focus=focus,
                state=state,
            )
            return {"status": r.status, "target_calls": r.target_calls,
                    "best_score": r.best_score, "winning_prompt": r.winning_prompt}
        if driver == "tap":
            r = T.run_tap(
                level,
                replace(brief),
                branch=args.branch,
                width=args.width,
                depth=args.depth,
                state=state,
            )
            win = r.winning_node.prompt if r.winning_node else None
            return {"status": r.status, "target_calls": r.target_calls,
                    "best_score": r.best_node.score if r.best_node else None, "winning_prompt": win}
        if driver == "gap":
            r = G.run_gap(
                level,
                replace(brief),
                branch=args.branch,
                width=args.width,
                depth=args.depth,
                state=state,
            )
            win = r.all_nodes[r.winning_node_idx].prompt if r.winning_node_idx is not None else None
            best = r.all_nodes[r.best_node_idx].score if r.best_node_idx is not None else None
            return {"status": r.status, "target_calls": r.target_calls, "best_score": best,
                    "winning_prompt": win}
        r = C.run_crescendo(
            level,
            replace(brief),
            turns=args.turns,
            campaign_state=state,
        )
        win = None
        if r.correct:
            # The arc is the technique; keep the attacker's turns in order.
            arc = [t.text for t in r.state.turns if t.role == "attacker"]
            win = " || ".join(f"turn {i}: {t}" for i, t in enumerate(arc, 1))
        return {"status": r.status, "target_calls": r.target_calls, "best_score": 10 if r.correct else None,
                "winning_prompt": win, "turns_used": r.turns_used}

    def run_ladder(arm: str, rep: int) -> dict[str, Any]:
        resuming = resume_checkpoint is not None
        run_id = (resume_checkpoint.run_id if resuming else
                  f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{arm}-{secrets.token_hex(3)}")
        run_dir = batch_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=resuming)
        trace = CampaignTrace(run_dir / "campaign.jsonl", run_id, resume=resuming)
        memory: list[dict[str, Any]] = []
        if resuming:
            memory = [
                {"technique": f"cleared gate {level} before resume",
                 "prompt": prompt, "level": int(level), "source": "run-memory"}
                for level, prompt in sorted(
                    resume_checkpoint.winning_prompts.items(),
                    key=lambda item: int(item[0]),
                    reverse=True,
                )
            ]
        T.LOG_PATH = run_dir / "probes.jsonl"
        T.SESSION_ID = run_id
        configure_arm(arm, memory)
        if resuming:
            T.PROGRESS_TOKEN = resume_checkpoint.progress_token

        manifest = {
            "run_id": run_id, "batch_id": batch_id, "repeat_index": rep, "arm": arm,
            "mode": mode.value, "oracle_accessed": mode == RunMode.AUTHOR_ORACLE,
            "started": datetime.now(timezone.utc).isoformat(),
            "chain": args.chain, "campaign_budget": args.campaign_budget,
            "gate_budget": args.gate_budget, "gate_hard_limit": args.gate_hard_limit,
            "tree": {"branch": args.branch, "width": args.width, "depth": args.depth},
            "pair_turns": args.pair_turns, "crescendo_turns": args.turns,
            "attacker_model": args.attacker_model, "judge_model": args.attacker_model,
            "evidence_analyst": {
                "enabled": not args.no_semantic_analyst,
                "model": args.attacker_model if not args.no_semantic_analyst else None,
                "grounding": "exact response support quote required",
            },
            "attacker_sampling": "no sampling parameters; adaptive thinking, effort high",
            "lab": {"base": args.base, "health": health, "progression_enforced": enforced,
                    "git_rev": git_rev(args.lab_repo), "models": lab_models or None,
                    "lab_run_id": lab_run.get("lab_run_id"),
                    "password_fingerprint": lab_run.get("password_fingerprint"),
                    "capabilities": {
                        "input": ["text"],
                        "conversation_state": False,
                        "tools": False,
                        "retrieval": False,
                        "file_uploads": False,
                        "image_input": False,
                        "audio_input": False,
                    }},
            "attacker_system_sha": {"tap": _sha(T._TAP_ATTACKER_SYSTEM), "gap": _sha(G._GAP_ATTACKER_SYSTEM),
                                    "crescendo": _sha(C._CRESCENDO_ATTACKER_SYSTEM)},
            "seeds": {"count": len(T._SEEDS), "sha": _sha(json.dumps(T._SEEDS, sort_keys=True))},
            "knowledge_tiers": dict(Counter(classify_seed(s).value for s in T._SEEDS)),
            "driver_source_sha": {d: _sha((OPERATOR / d / f"{d}.py").read_text()) for d in DRIVERS},
        }
        if not resuming:
            (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            trace.append(
                "campaign-started",
                knowledge_arm=arm,
                repeat_index=rep,
                budget={"target_chats_campaign": args.campaign_budget,
                        "target_chats_per_gate_soft": args.gate_budget,
                        "target_chats_per_gate_hard": args.gate_hard_limit,
                        "max_level": args.max_level},
                strategy_chain=args.chain,
                defense_revision=manifest["lab"],
                attacker={"model": args.attacker_model, "system_sha": manifest["attacker_system_sha"]},
                corpus={"seed_count": manifest["seeds"]["count"], "seed_sha": manifest["seeds"]["sha"]},
                classifier={"technique_family_version": 1, "response_class_version": 1},
                research_objectives=["disclose", "infer"],
            )
            (run_dir / "seeds-used.jsonl").write_text(
                "".join(json.dumps(s) + "\n" for s in T._SEEDS))
            if arm in arm_dropped:
                (run_dir / "seeds-dropped.jsonl").write_text(
                    "".join(json.dumps(s) + "\n" for s in arm_dropped[arm]))

        checkpoint = resume_checkpoint or CampaignCheckpoint(
            run_id=run_id,
            lab_fingerprint=active_lab_fingerprint,
            mode=mode.value,
            oracle_accessed=mode == RunMode.AUTHOR_ORACLE,
        )
        gates: list[dict[str, Any]] = list(checkpoint.gates)
        stopped_at = None
        campaign_spent = checkpoint.target_calls
        checkpoint_store.save(checkpoint)
        print(f"\n=== {run_id}  (ladder {rep + 1}/{args.repeat})")
        for level in range(checkpoint.current_level, args.max_level + 1):
            brief = T.AttackerBrief(level=level, **public_brief_fields(level, meta))
            row: dict[str, Any] = {"level": level, "target": target_model_for(level, lab_models),
                                   "attempts": [], "cleared": False, "cleared_by": None,
                                   "chats_by_driver": {d: 0 for d in args.chain}}
            saved_gate_state = checkpoint.gate_states.get(str(level))
            gate_state = (GateState.from_checkpoint(saved_gate_state)
                          if saved_gate_state else GateState(level=level))
            spent = checkpoint.gate_calls.get(str(level), 0)
            campaign_remaining = args.campaign_budget - campaign_spent
            if campaign_remaining <= 0:
                stopped_at = level
                break
            gate_cap = restored_gate_cap(
                spent=spent,
                campaign_remaining=campaign_remaining,
                gate_budget=args.gate_budget,
                gate_hard_limit=args.gate_hard_limit,
                has_progress=any(
                    observation.response_class.value in {"guard-block", "partial-leak"}
                    for observation in gate_state.observations
                ),
            )
            trace.append("gate-started", level=level, target=row["target"])
            scheduler = HypothesisScheduler()
            if "pair" in args.chain:
                if memory:
                    previous = memory[0]
                    scheduler.add(Hypothesis(
                        hypothesis_id=f"L{level}-previous-gate-transfer",
                        family="previous-gate-transfer",
                        strategy="pair",
                        prompt=str(previous["prompt"]),
                        previous_gate_transfer=4.0,
                        estimated_cost=args.pair_turns,
                    ))
                eligible = [seed for seed in T._SEEDS
                            if seed.get("level") in (None, level)]
                for index, seed in enumerate(eligible):
                    card_id = str(seed.get("card_id") or f"seed-{index}")
                    scheduler.add(Hypothesis(
                        hypothesis_id=f"L{level}-{card_id}",
                        family=str(seed.get("technique") or "other"),
                        strategy="pair",
                        prompt=str(seed.get("prompt") or ""),
                        public_prior=3.0,
                        estimated_cost=args.pair_turns,
                    ))
                if not eligible and not memory:
                    scheduler.add(Hypothesis(
                        hypothesis_id=f"L{level}-pair-cold",
                        family="adaptive-discovery",
                        strategy="pair",
                        public_prior=2.0,
                        estimated_cost=args.pair_turns,
                    ))
            for index, driver in enumerate(args.chain):
                if driver == "pair":
                    continue
                scheduler.add(Hypothesis(
                    hypothesis_id=f"L{level}-{driver}-tool",
                    family=f"{driver}-exploration",
                    strategy=driver,
                    public_prior=max(1.0 - (index * 0.2), 0.1),
                    estimated_cost=worst_case[driver],
                ))

            saved_hypotheses = checkpoint.hypothesis_observations.get(str(level), {})
            for hypothesis_id, observation_indexes in saved_hypotheses.items():
                if hypothesis_id not in scheduler:
                    continue
                for observation_index in observation_indexes:
                    if 0 <= observation_index < len(gate_state.observations):
                        scheduler.record(hypothesis_id, gate_state.observations[observation_index])

            driver_attempts = trace.driver_attempt_counts(level)
            while gate_cap - spent > 0:
                selection = scheduler.next()
                if selection is None:
                    break
                hypothesis, score_terms = selection
                driver = hypothesis.strategy
                if hypothesis.estimated_cost > gate_cap - spent:
                    hypothesis.disabled = True
                    continue
                driver_attempts[driver] += 1
                n = driver_attempts[driver]
                trace.append(
                    "strategy-selected",
                    level=level,
                    driver=driver,
                    driver_attempt=n,
                    reason="hypothesis-score",
                    hypothesis_id=hypothesis.hypothesis_id,
                    hypothesis_family=hypothesis.family,
                    score_terms=score_terms,
                    remaining_target_chats=gate_cap - spent,
                    evidence_state=gate_state.to_dict(),
                )
                t0 = time.time()
                observation_start = len(gate_state.observations)
                a = run_driver(driver, level, brief, hypothesis.prompt, gate_state)
                new_observations = gate_state.observations[observation_start:]
                hypothesis_map = checkpoint.hypothesis_observations.setdefault(str(level), {})
                hypothesis_indexes = hypothesis_map.setdefault(hypothesis.hypothesis_id, [])
                for observation in new_observations:
                    scheduler.record(hypothesis.hypothesis_id, observation)
                hypothesis_indexes.extend(
                    range(observation_start, observation_start + len(new_observations)))
                for observation_index, observation in enumerate(new_observations, 1):
                    trace.append(
                        "observation-recorded",
                        attempt_id=f"L{level}-{driver}-{n}-{observation_index}",
                        level=level,
                        driver=driver,
                        driver_attempt=n,
                        hypothesis_id=hypothesis.hypothesis_id,
                        **observation_payload(
                            observation,
                            classification=classify_technique(
                                observation.prompt,
                                driver=driver,
                                has_prior_evidence=observation_start > 0,
                            ),
                        ),
                    )
                spent += a["target_calls"]
                campaign_spent += a["target_calls"]
                row["chats_by_driver"][driver] += a["target_calls"]
                row["attempts"].append({
                    "driver": driver,
                    "attempt": n,
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "hypothesis_family": hypothesis.family,
                    "selection_score_terms": score_terms,
                    **{k: v for k, v in a.items() if k != "winning_prompt"},
                    "new_evidence": [o.response_class.value for o in new_observations],
                    "seconds": round(time.time() - t0, 1),
                })
                T._log({"event": "ladder_attempt", "run_id": run_id, "level": level,
                        "driver": driver, "attempt": n,
                        "hypothesis_id": hypothesis.hypothesis_id,
                        "status": a["status"], "target_calls": a["target_calls"]})
                trace.append(
                    "strategy-attempt-finished",
                    level=level,
                    driver=driver,
                    driver_attempt=n,
                    hypothesis_id=hypothesis.hypothesis_id,
                    status=a["status"],
                    target_calls=a["target_calls"],
                    response_classes=[o.response_class.value for o in new_observations],
                )
                if any(o.response_class.value in {"guard-block", "partial-leak"}
                       for o in new_observations):
                    gate_cap = min(
                        args.gate_hard_limit,
                        spent + (args.campaign_budget - campaign_spent),
                    )
                print(f"  gate {level} {driver} hypothesis {hypothesis.family}: {a['status']} "
                      f"({a['target_calls']} chats, {spent}/{gate_cap} gate; "
                      f"{campaign_spent}/{args.campaign_budget} campaign)")
                if a["target_calls"] == 0:
                    row["harness_error"] = True
                    checkpoint.current_level = level
                    checkpoint.progress_token = T.PROGRESS_TOKEN
                    checkpoint.target_calls = campaign_spent
                    checkpoint.gate_calls[str(level)] = spent
                    checkpoint.gate_states[str(level)] = gate_state.to_checkpoint()
                    checkpoint_store.save(checkpoint)
                    break
                if a["status"] == "PASS" and a["winning_prompt"]:
                    winning_technique = classify_technique(
                        a["winning_prompt"],
                        driver=driver,
                        has_prior_evidence=observation_start > 0,
                    ).to_dict()
                    row.update(
                        cleared=True,
                        cleared_by=driver,
                        winning_prompt=a["winning_prompt"],
                        winning_technique=winning_technique,
                        selected_hypothesis={
                            "id": hypothesis.hypothesis_id,
                            "family": hypothesis.family,
                        },
                    )
                    memory.insert(0, {
                        "technique": f"cleared gate {level} earlier in this run ({driver})",
                        "prompt": a["winning_prompt"], "level": level, "source": "run-memory",
                    })
                    checkpoint.winning_prompts[str(level)] = a["winning_prompt"]
                checkpoint.current_level = level
                checkpoint.progress_token = T.PROGRESS_TOKEN
                checkpoint.target_calls = campaign_spent
                checkpoint.gate_calls[str(level)] = spent
                checkpoint.gate_states[str(level)] = gate_state.to_checkpoint()
                checkpoint_store.save(checkpoint)
                if row["cleared"]:
                    break
            row["target_calls"] = spent
            row["evidence_state"] = gate_state.to_dict()
            gates.append(row)
            checkpoint.gates = gates
            checkpoint.target_calls = campaign_spent
            checkpoint.progress_token = T.PROGRESS_TOKEN
            if row["cleared"]:
                checkpoint.current_level = level + 1
                checkpoint.highest_cleared = level
                checkpoint.gate_states.pop(str(level), None)
                checkpoint.gate_calls.pop(str(level), None)
                checkpoint.hypothesis_observations.pop(str(level), None)
            else:
                checkpoint.current_level = level
                checkpoint.gate_states[str(level)] = gate_state.to_checkpoint()
                checkpoint.gate_calls[str(level)] = spent
            checkpoint_store.save(checkpoint)
            trace.append(
                "gate-finished",
                level=level,
                cleared=row["cleared"],
                cleared_by=row["cleared_by"],
                target_calls=spent,
                harness_error=bool(row.get("harness_error")),
                evidence_state=row["evidence_state"],
                selected_hypothesis=row.get("selected_hypothesis"),
                winning_technique=row.get("winning_technique"),
            )
            if row.get("harness_error") or not row["cleared"]:
                stopped_at = None if row.get("harness_error") else level
                break

        harness_error = any(g.get("harness_error") for g in gates)
        summary = {**manifest, "finished": datetime.now(timezone.utc).isoformat(),
                   "harness_error": harness_error,
                   "highest_cleared": max((g["level"] for g in gates if g["cleared"]), default=0),
                   "stopped_at": stopped_at,
                   "target_calls": sum(g["target_calls"] for g in gates),
                   "gates": gates}
        trace.append(
            "campaign-finished",
            status="harness-error" if harness_error else ("held" if stopped_at else "cleared"),
            highest_cleared=summary["highest_cleared"],
            stopped_at=stopped_at,
            target_calls=summary["target_calls"],
        )
        if not harness_error and stopped_at is None:
            # A completed campaign cannot resume into another requested gate.
            # Do not retain its bearer credential in the private checkpoint.
            checkpoint.progress_token = None
            checkpoint_store.save(checkpoint)
        summary["campaign_trace"] = {
            "path": "campaign.jsonl",
            "validation_errors": validate_trace(trace.path),
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        if harness_error:
            print(f"  -> HARNESS ERROR at gate {gates[-1]['level']}: no chat reached the lab, so this is "
                  f"not a result. First error is in {run_dir / 'probes.jsonl'}")
        else:
            by = ", ".join(f"{g['level']}:{g['cleared_by']}" for g in gates if g["cleared"]) or "none"
            print(f"  -> cleared through gate {summary['highest_cleared']}"
                  + (f", held at gate {stopped_at}" if stopped_at else ", all gates cleared")
                  + f"  ({summary['target_calls']} chats; cleared by {by})")
        return summary

    def write_batch(status: str) -> None:
        per_arm: dict[str, Any] = {}
        for arm in arms:
            rs = [r for r in results if r["arm"] == arm and not r["harness_error"]]
            if not rs:
                continue
            hc = [r["highest_cleared"] for r in rs]
            cleared_by: dict[int, Counter] = {}
            for r in rs:
                for g in r["gates"]:
                    if g["cleared"]:
                        cleared_by.setdefault(g["level"], Counter())[g["cleared_by"]] += 1
            per_arm[arm] = {
                "ladders": len(rs), "highest_cleared": hc, "median_highest_cleared": statistics.median(hc),
                "min": min(hc), "max": max(hc),
                "stopped_at": Counter(str(r["stopped_at"]) for r in rs),
                "cleared_by_driver_per_gate": {str(k): dict(v) for k, v in sorted(cleared_by.items())},
                "target_calls": [r["target_calls"] for r in rs],
            }
        batch = {"batch_id": batch_id, "status": status, "mode": mode.value,
                 "arms": arms, "repeat": args.repeat,
                 "chain": args.chain, "campaign_budget": args.campaign_budget,
                 "gate_budget": args.gate_budget, "gate_hard_limit": args.gate_hard_limit,
                 "attacker_model": args.attacker_model, "lab_git_rev": git_rev(args.lab_repo),
                 "lab_models": lab_models or None,
                 "runs": [{"run_id": r["run_id"], "arm": r["arm"], "highest_cleared": r["highest_cleared"],
                           "stopped_at": r["stopped_at"], "harness_error": r["harness_error"],
                           "target_calls": r["target_calls"]} for r in results],
                 "per_arm": per_arm}
        (batch_dir / "batch.json").write_text(json.dumps(batch, indent=2) + "\n")
        print(f"\n=== batch {batch_id} ({status})")
        for arm, s in per_arm.items():
            print(f"  {arm:8s} highest cleared per ladder {s['highest_cleared']}  median {s['median_highest_cleared']}"
                  f"  chats {s['target_calls']}")
            for lvl, c in s["cleared_by_driver_per_gate"].items():
                print(f"           gate {lvl}: " + ", ".join(f"{d} x{k}" for d, k in c.items()))
        print(f"  {batch_dir / 'batch.json'}")

    for rep in range(args.repeat):
        for arm in arms:
            summary = run_ladder(arm, rep)
            results.append(summary)
            if summary["harness_error"]:
                # Usually systemic (API key, model access, SDK change), so stop
                # rather than spend the rest of the batch on the same failure.
                write_batch("stopped: harness error")
                return 1
    write_batch("complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
