from typing import Any, Literal
from pydantic import BaseModel, Field

DecisionStatus = Literal["ALLOWED", "DENIED", "ESCALATED"]

class Actor(BaseModel):
    user_id: str
    role: str = "employee"

class DecisionRequest(BaseModel):
    action: str
    actor: Actor
    resource: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    run_id: str | None = None

class PolicyDecision(BaseModel):
    decision_id: str
    status: DecisionStatus
    action: str
    rule_ids: list[str] = Field(default_factory=list)
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    recommended_next_step: str = "Continue the workflow."
    timestamp: str

class RedTeamRequest(BaseModel):
    scenario_id: str | None = None
    prompt: str | None = None
    receipt_text: str | None = None
    actor: Actor = Field(default_factory=lambda: Actor(user_id="JUDGE", role="admin"))
    run_id: str | None = None

class AuditEvent(BaseModel):
    event_id: int
    timestamp: str
    run_id: str | None
    event_type: str
    actor_id: str | None
    payload: dict[str, Any]
    previous_hash: str
    event_hash: str

class EventEnvelope(BaseModel):
    event: str
    data: dict[str, Any]
