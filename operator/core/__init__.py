"""Shared evidence and campaign state for Warden attack strategies."""

from .analyst import ANALYST_SYSTEM, AnalystResult, HybridEvidenceAnalyst

from .evidence import (
    AdaptiveSelectionPolicy,
    AdaptiveEscalationPolicy,
    Candidate,
    Evidence,
    GateState,
    Observation,
    ResponseClass,
    grounded_candidate,
    observe_attempt,
)
from .trace import (
    CampaignTrace,
    TRACE_SCHEMA,
    TRACE_SCHEMA_VERSION,
    observation_payload,
    validate_trace,
)
from .taxonomy import (
    Interaction,
    Objective,
    Representation,
    Strategy,
    TAXONOMY_SCHEMA,
    TAXONOMY_VERSION,
    TechniqueClassification,
    classify_technique,
)

__all__ = [
    "AdaptiveSelectionPolicy",
    "AdaptiveEscalationPolicy",
    "Candidate",
    "Evidence",
    "GateState",
    "Observation",
    "ResponseClass",
    "grounded_candidate",
    "observe_attempt",
    "CampaignTrace",
    "TRACE_SCHEMA",
    "TRACE_SCHEMA_VERSION",
    "observation_payload",
    "validate_trace",
    "Interaction",
    "Objective",
    "Representation",
    "Strategy",
    "TAXONOMY_SCHEMA",
    "TAXONOMY_VERSION",
    "TechniqueClassification",
    "classify_technique",
    "ANALYST_SYSTEM",
    "AnalystResult",
    "HybridEvidenceAnalyst",
]
