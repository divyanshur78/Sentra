# Person 3 integration handoff

## Ownership boundary
Person 1 owns expense-domain logic and deterministic R1–R9 evaluators.
Person 3 owns the central gateway, R10 prompt-injection/poisoned-receipt defence,
red-team engine, immutable/hash-chained audit, evaluation APIs, and SSE/WebSocket updates.

## Shared interface
`app/integrations/governance_port.py` defines:
- `authorize_tool_call(call: ToolCall) -> PolicyDecision`
- `record_event(event_type, message, actor_id, run_id, claim_id, payload)`
- `metrics() -> dict`
- `run_redteam(payload) -> dict`

Schemas are in `app/schemas.py`. Preserve ToolCall fields and PolicyDecision decision values:
`ALLOWED`, `DENIED`, `ESCALATED`.

## Plug in Person 3 implementation
1. Create `Person3GovernanceAdapter` implementing `GovernancePort`.
2. In `app/integrations/provider.py`, instantiate it instead of `LocalGovernanceAdapter`.
3. Route every state-changing/protected tool call through the gateway.
4. Gateway should invoke Person 1 evaluators from `app/services/policy_rules.py`.
5. Do not duplicate R1–R9 rule definitions in the gateway; Person 3 owns interception, R10 and decision orchestration.
6. Do not execute a tool action for `DENIED` or `ESCALATED`.
7. Replace local audit with append-only hash-chain audit. Local adapter is only a demo fallback.

## Person 1 policy functions
- `evaluate_claim_rules(db, claim, items)` — R1–R7
- `check_employee_scope(requester_id, resource_owner_id)` — R8
- `check_manager_assignment(manager_id, claim)` — R9

## Suggested audit event names
`USER_REQUEST_RECEIVED`, `MEMORY_LOOKUP`, `RECEIPT_UPLOADED`, `RECEIPT_EXTRACTED`,
`LLM_PLAN_CREATED`, `TOOL_CALL_REQUESTED`, `POLICY_ALLOWED`, `POLICY_DENIED`,
`POLICY_ESCALATED`, `APPROVAL_REQUESTED`, `MANAGER_APPROVED`, `MANAGER_REJECTED`,
`CLAIM_SUBMITTED`, `CLAIM_BLOCKED`, `REDTEAM_ATTACK`, `EVALUATION_COMPLETED`.

## Frontend contract
Base URL: `http://127.0.0.1:8000`; docs: `/docs`.

Draft JSON:
```json
{
  "employee_id":"emp-001",
  "title":"Bangalore client visit",
  "purpose":"Client meeting",
  "items":[{
    "receipt_id":"rcpt-id-from-upload",
    "vendor":"Hotel ABC",
    "date":"2026-11-03",
    "amount":4200,
    "category":"lodging"
  }]
}
```
Submit: `{"employee_id":"emp-001","confirmation":true}`
Approve/reject: `{"manager_id":"mgr-001","reason":"Reviewed receipts"}`

## Current limits
Demo login is not secure production authentication. Receipt parser/OCR is heuristic and fields must be reviewed. Gemini is optional. Person 3 must complete R10, red-team, immutable audit, and full evaluation.
