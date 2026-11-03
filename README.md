<<<<<<< HEAD
# Sentra AI — Backend (Person 1)

Hackathon backend for the Governed ExpenseClaim Agent brief.

## Ownership
**Person 1:** FastAPI core, SQLite/mock ERP, employee memory, receipt extraction, LLM-assisted intent parsing, expense classification, agent workflow, draft/approval/rejection/submission lifecycle, deterministic R1–R9 rule evaluators.

**Person 3:** central policy gateway, R10 prompt-injection and red-team engine, immutable/hash-chained audit, evaluation APIs, streaming updates, integration reliability.

Person 1 provides R1–R9 domain evaluators. Person 3 owns the gateway that intercepts tool calls and calls these evaluators. Do not build a second gateway in Person 1's code.

## Windows setup
```powershell
cd SentraAI_Backend_Person1
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```
Docs: http://127.0.0.1:8000/docs | Health: http://127.0.0.1:8000/health

Demo users: employee `emp-001`, manager `mgr-001`, second employee `emp-002`, second manager `mgr-002`.

## Main endpoints
- `POST /api/auth/login`
- `POST /api/chat`
- `POST /api/receipts/upload?employee_id=emp-001` (multipart key `files`)
- `POST /api/claims/draft`
- `GET /api/claims/{claim_id}?requester_id=emp-001`
- `POST /api/claims/{claim_id}/submit`
- `POST /api/claims/{claim_id}/approve`
- `POST /api/claims/{claim_id}/reject`
- `POST /api/claims/{claim_id}/finalize`
- `GET /api/agent/trace/{run_id}?requester_id=emp-001`
- `GET /api/memory/{employee_id}?requester_id=emp-001`
- `GET /api/policy/rules`
- `GET /api/admin/metrics`
- `GET /api/admin/policy-decisions`
- `POST /api/redteam/run`

## Integration
See `docs/PERSON3_INTEGRATION.md`. Person 3 implements `GovernancePort` in `app/integrations/governance_port.py` and swaps the adapter in `app/integrations/provider.py`. Preserve `ToolCall` and `PolicyDecision` field names and decision values `ALLOWED`, `DENIED`, `ESCALATED`.

## Notes
This is a demo mock ERP, not production finance software. Demo login is not real authentication. Receipt extraction uses OCR/text heuristics and must be reviewed by the employee. Set `GEMINI_API_KEY` in `.env` for optional Gemini request interpretation; local fallback works without it. Never commit `.env`.
=======
# Sentra
Governed AI agents for secure, intelligent, and human-controlled task automation.
>>>>>>> 51f644a839708acd19ab0d013242bfbd053ffb59
