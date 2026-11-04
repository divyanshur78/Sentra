import asyncio
import json
import os
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from .metrics import build_metrics
from .redteam import SCENARIOS
from .runtime import audit_store, gateway, redteam
from .schemas import DecisionRequest, RedTeamRequest

router = APIRouter(prefix="/governance", tags=["governance"])

@router.get("/health")
def health():
    return {"status": "ok", "service": "person3-governance"}

@router.post("/decision")
def evaluate_decision(body: DecisionRequest):
    return gateway.evaluate(body.action, body.actor.model_dump(), body.resource, body.context, body.run_id).model_dump()

@router.post("/redteam/run")
def run_redteam(body: RedTeamRequest):
    try:
        return redteam.run(body.scenario_id, body.prompt, body.receipt_text,
                           body.actor.model_dump(), body.run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.get("/redteam/scenarios")
def redteam_scenarios():
    return [{"scenario_id": k, "label": v["label"], "expected": v["expected"]}
            for k, v in SCENARIOS.items()]

@router.get("/audit")
def get_audit(limit: int = Query(100, ge=1, le=1000), run_id: str | None = None,
              event_type: str | None = None):
    return {"events": audit_store.list_events(limit, run_id, event_type)}

@router.get("/audit/verify")
def verify_audit():
    return audit_store.verify()

@router.get("/trace/{run_id}")
def get_trace(run_id: str):
    return {"run_id": run_id, "events": audit_store.list_events(limit=1000, run_id=run_id)}

@router.get("/metrics")
def metrics():
    # Include Person 1 claim counts alongside Person 3 governance metrics.
    from app.integrations.provider import get_governance
    return get_governance().metrics()

@router.get("/policy-decisions")
def policy_decisions(limit: int = Query(100, ge=1, le=1000)):
    return {"decisions": audit_store.list_events(limit, event_type="policy_decision")}

@router.post("/events")
def record_integration_event(body: dict):
    event_type = str(body.get("event_type", "agent_status"))
    if event_type not in {"agent_status", "tool_call_requested", "tool_call_result",
                          "human_approval", "claim_submitted", "evaluation_result"}:
        raise HTTPException(status_code=400, detail="Unsupported event_type")
    event = audit_store.append(event_type, body.get("payload", {}),
                               body.get("actor_id"), body.get("run_id"))
    return event

@router.get("/events")
async def stream_events(run_id: str | None = None):
    async def event_generator():
        last_id = 0
        # Polling-backed SSE; suitable for hackathon demos and a single service instance.
        while True:
            events = audit_store.list_events(limit=1000, run_id=run_id)
            fresh = [e for e in events if e["event_id"] > last_id]
            for event in fresh:
                last_id = event["event_id"]
                yield f"id: {last_id}\nevent: {event['event_type']}\ndata: {json.dumps(event, default=str)}\n\n"
            yield ": keep-alive\n\n"
            await asyncio.sleep(1.0)
    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

app = FastAPI(title="ExpenseClaim Governance Service", version="1.0.0")
origins = [x.strip() for x in os.getenv("GOVERNANCE_CORS_ORIGINS",
          "http://localhost:3000,http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")

@app.get("/health")
def root_health():
    return health()
