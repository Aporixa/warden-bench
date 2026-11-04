# Campaign trace schema

This reference describes version 1 of `warden.campaign-trace`. Each line is one JSON object. Event order is significant.

## Event envelope

Every event has these fields:

| field | type | meaning |
|---|---|---|
| `schema` | string | Always `warden.campaign-trace`. |
| `schema_version` | integer | Currently `1`. |
| `campaign_id` | string | Stable identifier for one campaign. |
| `sequence` | integer | Contiguous sequence that starts at `1`. |
| `recorded_at` | string | UTC timestamp in ISO 8601 format. |
| `event_type` | string | Event name from the table below. |
| `data` | object | Fields specific to the event. |

## Event types

| event | required meaning |
|---|---|
| `campaign-started` | Declares the knowledge arm, budget, strategy chain, defense revision, attacker, and corpus identity. |
| `gate-started` | Identifies the gate and target model under evaluation. |
| `strategy-selected` | Records which driver was selected, why it was selected, its attempt number, the remaining budget, and the evidence available at that decision. |
| `observation-recorded` | Preserves a stable attempt identifier, input text, target response, versioned multi-axis technique classification, response class, extracted evidence, candidate, and verification status. |
| `strategy-attempt-finished` | Records one driver invocation, its cost, outcome classes, and adaptive budget decision. |
| `gate-finished` | Records whether the gate cleared, the responsible driver, cost, accumulated evidence state, and, for current traces, the selected hypothesis and classified winning technique. |
| `campaign-finished` | Records the terminal state, highest cleared gate, stopping gate, and total target calls. |

A stopped process can leave a trace without `campaign-finished`. The trace remains useful, but a publication must mark the campaign as incomplete.

## Validation

`core.validate_trace()` checks the schema identifier, version, campaign identity, event order, and sequence continuity. It does not decide whether a finding is scientifically valid.

The trace retains raw text so an analyst can reproduce classifications. A publication process must create a sanitized derivative. It must not modify the raw trace.

The selected hypothesis describes the controller prior that allocated an
attempt. It is not proof that the generated attempt used that technique. Use
the observation's classified technique, and the gate's `winning_technique` in
current traces, when attributing generated behavior. Older traces can lack
these newer fields and must be identified by their source revision.
