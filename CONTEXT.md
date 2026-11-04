# Warden Bench

Warden Bench studies how adaptive attacks learn from defended chat systems and how defenses change under repeated evaluation.

## Language

**Attempt**:
One input delivered to a target as part of a campaign.
_Avoid_: Prompt, probe

**Observation**:
The target response, its classification, and evidence extracted from one attempt.
_Avoid_: Result, score

**Campaign**:
An ordered sequence of attempts, observations, and decisions made under one budget against one defense revision.
_Avoid_: Run, attack

**Finding**:
A reproducible claim supported by one or more campaigns.
_Avoid_: Win, anecdote

**Defense revision**:
The identifiable target configuration evaluated by a campaign, including its code revision and model configuration.
_Avoid_: Target version

**Seed**:
Starting material that can inform an attempt. A seed is an input to research and is not a finding.
_Avoid_: Dataset, exploit

**Knowledge arm**:
A declared limit on information available to an attacker during a campaign.
_Avoid_: Corpus tier, access level

**Technique family**:
A behavioral class assigned to an attempt without depending on its exact wording.
_Avoid_: Prompt category

**Evidence**:
A fact inferred only from information that the target exposed during a campaign.
_Avoid_: Hint, telemetry

**Publication review**:
A named human decision that a campaign may enter a dataset release after inspection for secrets, licensing, and provenance.
_Avoid_: Approval flag, automated review

**Dataset release**:
An immutable, licensed selection of reviewed campaign observations with declared temporal splits and source identities.
_Avoid_: Seed dump, export

**Temporal cutoff**:
The instant that assigns an entire campaign to the training or held-out split according to the campaign start time.
_Avoid_: Random split, row split
