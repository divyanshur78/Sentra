from typing import Any
from app.schemas import ToolCall, PolicyDecision
from app.services.policy_rules import evaluate_claim_rules
from app.db import get_db
from app.utils import new_id, now_iso, dumps, loads

class LocalGovernanceAdapter:
    """Standalone development adapter. Not a substitute for Person 3's real gateway."""
    def authorize_tool_call(self, call: ToolCall) -> PolicyDecision:
        if call.tool_name == "submit_claim" and call.claim_id:
            with get_db() as db:
                row = db.execute("SELECT * FROM claims WHERE id=?", (call.claim_id,)).fetchone()
                if not row:
                    return PolicyDecision(decision="DENIED", rule_ids=["R0"], reasons=["Claim not found"], risk_level="HIGH")
                result = evaluate_claim_rules(db, row, loads(row["items_json"], []))
                if result["decision"] != "ALLOWED":
                    return PolicyDecision(**result)
        return PolicyDecision(decision="ALLOWED", reasons=["Local adapter allowed this call; replace with Person 3 gateway."])

    def record_event(self, event_type: str, message: str, *, actor_id="", run_id=None, claim_id=None, payload=None):
        with get_db() as db:
            db.execute("""INSERT INTO audit_events
              (id,run_id,claim_id,actor_id,event_type,message,payload_json,created_at)
              VALUES (?,?,?,?,?,?,?,?)""",
              (new_id("evt"),run_id,claim_id,actor_id,event_type,message,dumps(payload or {}),now_iso()))

    def metrics(self):
        with get_db() as db:
            total=db.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
            submitted=db.execute("SELECT COUNT(*) FROM claims WHERE status='SUBMITTED'").fetchone()[0]
            pending=db.execute("SELECT COUNT(*) FROM claims WHERE status='PENDING_APPROVAL'").fetchone()[0]
            events=db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        return {"total_claims":total,"submitted_claims":submitted,"pending_approvals":pending,"audit_events":events}

    def run_redteam(self, payload):
        return {"status":"NOT_IMPLEMENTED","message":"Person 3 must connect the red-team engine."}
