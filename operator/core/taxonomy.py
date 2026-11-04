"""Warden-native, multi-axis classification of attack behavior."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


TAXONOMY_SCHEMA = "warden.technique-classification"
TAXONOMY_VERSION = 1


class Objective(StrEnum):
    DISCLOSE = "disclose"
    INFER = "infer"
    OVERRIDE = "override"
    IMPERSONATE = "impersonate"
    INVOKE = "invoke"
    PERSIST = "persist"
    UNKNOWN = "unknown"


class Strategy(StrEnum):
    DIRECT = "direct-request"
    REFRAMING = "reframing"
    DECOMPOSITION = "decomposition"
    INDIRECTION = "indirection"
    TRANSFORMATION = "transformation"
    GRADUAL_ELICITATION = "gradual-elicitation"
    AUTHORITY_CLAIM = "authority-claim"
    ROLEPLAY = "roleplay"
    COMPLETION = "completion"
    OTHER = "other"


class Representation(StrEnum):
    PLAIN = "plain-text"
    ENCODED = "encoded"
    STRUCTURED = "structured"
    QUOTED = "quoted"
    MULTILINGUAL = "multilingual"
    NOISY = "noisy"


class Interaction(StrEnum):
    SINGLE_TURN = "single-turn"
    REFINEMENT = "refinement"
    BRANCHING = "branching"
    EVIDENCE_DRIVEN = "evidence-driven"
    CONFIRMATION = "confirmation"
    EMBEDDED_TRANSCRIPT = "embedded-transcript"


@dataclass(frozen=True)
class TechniqueClassification:
    objectives: tuple[Objective, ...]
    strategies: tuple[Strategy, ...]
    representations: tuple[Representation, ...]
    interactions: tuple[Interaction, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": TAXONOMY_SCHEMA,
            "schema_version": TAXONOMY_VERSION,
            "objectives": [value.value for value in self.objectives],
            "strategies": [value.value for value in self.strategies],
            "representations": [value.value for value in self.representations],
            "interactions": [value.value for value in self.interactions],
        }


def _contains(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)


def classify_technique(
    attempt: str,
    *,
    objectives: tuple[Objective, ...] | None = None,
    driver: str | None = None,
    has_prior_evidence: bool = False,
) -> TechniqueClassification:
    """Classify observable behavior without using target internals."""

    text = attempt.casefold()
    inferred_objectives: list[Objective] = []
    strategies: list[Strategy] = []
    representations: list[Representation] = []
    interactions: list[Interaction] = []

    if objectives is None:
        if _contains(text, ("length", "how many", "first letter", "position", "property", "confirm", "is it")):
            inferred_objectives.append(Objective.INFER)
        if _contains(text, ("password", "secret", "watchword", "guarded word", "say", "output", "spell", "encode", "translate")):
            inferred_objectives.append(Objective.DISCLOSE)
        if _contains(text, ("ignore", "override", "system prompt", "previous instructions")):
            inferred_objectives.append(Objective.OVERRIDE)
        objectives = tuple(dict.fromkeys(inferred_objectives)) or (Objective.UNKNOWN,)

    if _contains(text, ("password", "secret", "watchword", "guarded word")):
        strategies.append(Strategy.DIRECT)
    if _contains(text, ("act as", "roleplay", "pretend", "persona", "you are now")):
        strategies.append(Strategy.ROLEPLAY)
    if _contains(text, ("auditor", "authorized", "authorization", "administrator", "developer")):
        strategies.append(Strategy.AUTHORITY_CLAIM)
    if _contains(text, ("complete", "continue", "fill in the blank", "finish this")):
        strategies.append(Strategy.COMPLETION)
    if _contains(text, ("letter at a time", "each letter", "letter 1", "characters separately", "acrostic")):
        strategies.append(Strategy.DECOMPOSITION)
    if _contains(text, ("translate", "encode", "base64", "hex", "cipher", "reverse", "pig latin")):
        strategies.append(Strategy.TRANSFORMATION)
    if _contains(text, ("story", "poem", "metaphor", "example", "hypothetical", "educational")):
        strategies.append(Strategy.REFRAMING)
    if _contains(text, ("indirect", "without saying", "allude", "synonym", "definition", "etymology")):
        strategies.append(Strategy.INDIRECTION)
    if driver == "crescendo":
        strategies.append(Strategy.GRADUAL_ELICITATION)
    if not strategies:
        strategies.append(Strategy.OTHER)

    if _contains(text, ("base64", "hex", "cipher", "encode", "rot13")):
        representations.append(Representation.ENCODED)
    if _contains(text, ("json", "xml", "yaml", "csv", "tool_call", "code block")):
        representations.append(Representation.STRUCTURED)
    if _contains(text, ("quote", "quoted", "verbatim", "dialogue")):
        representations.append(Representation.QUOTED)
    if _contains(text, ("translate", "french", "spanish", "german", "latin", "multilingual")):
        representations.append(Representation.MULTILINGUAL)
    if _contains(text, ("separator", "interleave", "spaces between", "punctuation between", "zero width")):
        representations.append(Representation.NOISY)
    if not representations:
        representations.append(Representation.PLAIN)

    if driver in {"tap", "gap"}:
        interactions.append(Interaction.BRANCHING)
    elif driver == "crescendo":
        interactions.append(Interaction.EMBEDDED_TRANSCRIPT)
    else:
        interactions.append(Interaction.SINGLE_TURN)
    if has_prior_evidence:
        interactions.append(Interaction.EVIDENCE_DRIVEN)
    if _contains(text, ("confirm", "verify", "is it", "did you mean")):
        interactions.append(Interaction.CONFIRMATION)

    return TechniqueClassification(
        objectives=objectives,
        strategies=tuple(dict.fromkeys(strategies)),
        representations=tuple(dict.fromkeys(representations)),
        interactions=tuple(dict.fromkeys(interactions)),
    )
