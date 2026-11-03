# Person 3 integration contract (without modifying Person 1 files in this package)

## Ownership split

- **Person 1 owns R1–R9** and the source-of-truth expense data: employees, claims, receipts, monthly/category limits, duplicates, employee scope, manager assignment.
- **Person 3 owns** the `GovernancePort` implementation, centralized action gateway, R10 untrusted-document inspection, hash-chained audit stream, red-team scenarios, governance metrics, and SSE endpoint.
- **Person 2 owns** the UI. The TypeScript client and endpoint contract are supplied separately in `frontend/governanceClient.ts`.

## Copy only Person 3 files

Copy the files from this package into the matching paths in the shared repository. Do not overwrite Person 1's files.

| Package path | Destination |
|---|---|
| `governance/*.py` | repository `governance/` |
| `app/integrations/person3_adapter.py` | repository `app/integrations/person3_adapter.py` |
| `frontend/governanceClient.ts` | repository `frontend/governanceClient.ts` |
| `tests/test_person3_integration.py` | repository `tests/test_person3_integration.py` |
| `docs/PERSON3_INTEGRATION.md` | repository `docs/PERSON3_INTEGRATION.md` |

## Existing Person 1 interface implemented

The adapter implements exactly the `GovernancePort` methods supplied by Person 1:

```python
authorize_tool_call(call: ToolCall) -> PolicyDecision
record_event(event_type, message, *, actor_id="", run_id=None,
             claim_id=None, payload=None) -> None
metrics() -> dict
run_redteam(payload: dict) -> dict
```

It uses Person 1's existing `app.schemas.ToolCall` and `app.schemas.PolicyDecision`, database access (`app.db.get_db`), utilities, and deterministic evaluators (`evaluate_claim_rules`, `check_employee_scope`, `check_manager_assignment`). It does not create a second R1–R9 policy source.

## Two activation hooks (not changed by this package)

These are the only expected application wiring changes when Person 1 is ready. They are intentionally not included as replacements in this Person 3-only package.

1. In `app/integrations/provider.py`, select the new adapter:

```python
from app.integrations.person3_adapter import Person3GovernanceAdapter
_governance = Person3GovernanceAdapter()
```

Keep Person 1's existing `get_governance()` and `set_governance()` functions.

2. In `app/main.py`, mount the governance router:

```python
from governance.api import router as governance_router
app.include_router(governance_router, prefix="/api")
```

The resulting governance endpoints are under `/api/governance/`.

## API endpoints for Person 2

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/governance/health` | Governance service health |
| POST | `/api/governance/decision` | Evaluate a policy action for diagnostics/demo |
| GET | `/api/governance/audit?limit=100` | Read recent hash-chained audit events |
| GET | `/api/governance/audit/verify` | Verify the audit hash chain |
| GET | `/api/governance/trace/{run_id}` | Read events for one run |
| GET | `/api/governance/policy-decisions` | List policy decision events |
| GET | `/api/governance/metrics` | Governance + claim metrics |
| GET | `/api/governance/redteam/scenarios` | List attack scenarios |
| POST | `/api/governance/redteam/run` | Run a red-team scenario |
| POST | `/api/governance/events` | Record a supported integration event |
| GET | `/api/governance/events` | Subscribe to server-sent events (SSE) |

The existing Person 1 routes such as `/api/admin/metrics` and `/api/redteam/run` continue to use the `GovernancePort` once the provider is switched.

## Person 2 frontend setup

Copy `frontend/governanceClient.ts` into Person 2's frontend source tree. Set:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

The client expects a Vite-compatible frontend. It exposes `governanceApi` methods and `subscribeGovernanceEvents()` for SSE. Person 2 should render decisions, audit verification, metrics, red-team results, and live event updates in their own components.

## Testing

From the combined Person 1 repository root after copying the files and activating the adapter:

```bash
pytest -q tests/test_person3_integration.py
```

The tests use Person 1's actual database and policy evaluator. They are integration tests for the backend adapter, not proof of production security or Person 2 UI compatibility.

## Security and demo limitations

- Person 1's current demo authentication uses user IDs in request payloads. Do not treat that as production-grade identity verification.
- The `/decision` diagnostic endpoint accepts actor/resource/context data supplied by its caller. It must not be used as a replacement for the trusted adapter on real workflow actions; protect admin/diagnostic endpoints with real authorization before deployment.
- R10 uses deterministic phrase/pattern checks against receipt/document text. It is a useful demo guard, not a complete prompt-injection detector.
- The SQLite audit chain detects modification of chained event content, but an attacker with filesystem/database access could rewrite the database and recompute the chain. Use OS access controls and external backups/anchoring for stronger tamper resistance.
- SSE currently polls the local SQLite audit store and is suitable for a single-process demo. A multi-worker deployment should use a shared event broker.
