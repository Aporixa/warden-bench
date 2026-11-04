# Technique classification reference

Version 1 of `warden.technique-classification` describes behavior across four independent axes. A classification can contain several values on each axis.

## Objectives

| value | meaning |
|---|---|
| `disclose` | Obtain protected content directly or through a transformed output. |
| `infer` | Learn constraints that reduce the possible protected content. |
| `override` | Replace or weaken an instruction that controls target behavior. |
| `impersonate` | Claim or construct an identity that should receive different treatment. |
| `invoke` | Cause the target to use an external capability. |
| `persist` | Cause attacker-controlled state to affect a later interaction. |
| `unknown` | The available record does not establish an objective. |

## Strategies

The strategy axis includes direct requests, reframing, decomposition, indirection, transformation, gradual elicitation, authority claims, roleplay, completion, and `other`.

## Representations

The representation axis includes plain text, encoded text, structured data, quoted text, multilingual text, and noisy text.

## Interactions

The interaction axis includes single-turn, refinement, branching, evidence-driven, confirmation, and embedded-transcript behavior.

Warden currently labels Crescendo as `embedded-transcript` because the target is stateless. The label describes what the target receives. It does not claim that the target retained conversational state.

## Classifier limits

The version 1 classifier uses explicit text markers and driver context. It creates reproducible labels, not ground truth. A dataset release retains the original attempt so reviewers can correct or replace derived labels in a later taxonomy version.
