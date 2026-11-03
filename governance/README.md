# Person 3 — Governance Drop-in Files

This package contains **only Person 3-owned files** for the SentraAI expense-claim project. It does not include, overwrite, or modify any Person 1 source files.

## Contents

```text
person3_dropin/
├── app/integrations/person3_adapter.py   # Implements Person 1's GovernancePort
├── governance/                            # Gateway, R10, audit, red-team, API, metrics
├── frontend/governanceClient.ts           # API client contract for Person 2
├── docs/PERSON3_INTEGRATION.md            # Exact copy destinations and activation notes
└── tests/test_person3_integration.py      # Integration tests to run in combined repo
```

## Copy destinations in the shared repository

Copy the contents of this package into the root of the Person 1 repository, preserving paths:

- `governance/` → repository-root `governance/`
- `app/integrations/person3_adapter.py` → `app/integrations/person3_adapter.py`
- `frontend/governanceClient.ts` → `frontend/governanceClient.ts`
- `docs/PERSON3_INTEGRATION.md` → `docs/PERSON3_INTEGRATION.md`
- `tests/test_person3_integration.py` → `tests/test_person3_integration.py`

The `app/` folder in this package contains only the Person 3 adapter file. Do not replace Person 1's `app/`, `app/integrations/provider.py`, schemas, services, routes, or database files.

## Important activation note

The uploaded Person 1 project currently defaults to `LocalGovernanceAdapter` in `app/integrations/provider.py`. The drop-in adapter implements the existing `GovernancePort`, but it will not become the active adapter until Person 1 changes the provider selection to instantiate `Person3GovernanceAdapter`. That one-line provider switch is intentionally **not included** here because you asked for Person 3 files only.

Similarly, the governance router must be mounted by the application to expose the `/api/governance/*` endpoints. Exact minimal activation instructions are in `docs/PERSON3_INTEGRATION.md`; no Person 1 files are modified by this package.

## Requirements

Uses Person 1's existing FastAPI, Pydantic v2, and SQLite dependencies. No new third-party package is required beyond Person 1's requirements.
