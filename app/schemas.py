from pydantic import BaseModel, Field
from typing import Any, Optional

class LoginRequest(BaseModel):
    user_id: str

class ChatRequest(BaseModel):
    employee_id: str
    message: str

class ExpenseItem(BaseModel):
    receipt_id: Optional[str] = None
    vendor: str
    date: Optional[str] = None
    amount: float = Field(gt=0)
    category: str
    description: Optional[str] = ""

class DraftClaimRequest(BaseModel):
    employee_id: str
    title: str
    purpose: str = ""
    cost_center: Optional[str] = None
    items: list[ExpenseItem]

class DecisionRequest(BaseModel):
    manager_id: str
    reason: str = ""

class SubmitRequest(BaseModel):
    employee_id: str
    confirmation: bool = True

class ToolCall(BaseModel):
    actor_id: str
    tool_name: str
    action: str
    resource_owner_id: Optional[str] = None
    claim_id: Optional[str] = None
    amount: Optional[float] = None
    metadata: dict[str, Any] = {}

class PolicyDecision(BaseModel):
    decision: str
    rule_ids: list[str] = []
    reasons: list[str] = []
    risk_level: str = "LOW"
    evidence: list[dict[str, Any]] = []

class RedTeamRequest(BaseModel):
    employee_id: str
    attack_type: str
    prompt: str
    receipt_text: Optional[str] = None
