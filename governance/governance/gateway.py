"""Deterministic policy enforcement boundary. Unknown actions are denied by default."""
from datetime import datetime, timezone
from uuid import uuid4
from .schemas import PolicyDecision

class PolicyGateway:
    def __init__(self, audit_store):
        self.audit = audit_store

    def evaluate(self, action: str, actor: dict, resource: dict | None = None,
                 context: dict | None = None, run_id: str | None = None) -> PolicyDecision:
        resource, context = resource or {}, context or {}
        role = str(actor.get("role", "employee")).lower()
        user_id = str(actor.get("user_id", ""))
        status, rules, reasons, risk, next_step = "ALLOWED", [], [], "LOW", "Continue the workflow."

        def deny(rule, reason, step="Correct the claim or contact Finance."):
            nonlocal status, risk, next_step
            status, risk, next_step = "DENIED", "HIGH", step
            rules.append(rule); reasons.append(reason)

        def escalate(rule, reason, step="Route the claim to the assigned manager for explicit approval."):
            nonlocal status, risk, next_step
            if status != "DENIED":
                status, risk, next_step = "ESCALATED", "HIGH", step
            rules.append(rule); reasons.append(reason)

        if action not in {"claim.submit", "claim.create_draft", "claim.read", "profile.read",
                          "claim.approve", "claim.reject"}:
            deny("R0", f"Unknown or unsupported action '{action}' is denied by default.",
                 "Register the action and define an explicit policy before enabling it.")

        # R8: employee can access only their own claim/profile.
        if action in {"claim.read", "profile.read"} and role == "employee":
            owner = resource.get("owner_id") or resource.get("employee_id")
            if owner and owner != user_id:
                deny("R8", "Employee attempted to access another employee's claim or profile.",
                     "Only access records belonging to the authenticated employee.")

        # R9: managers may act only on claims assigned to them.
        if action in {"claim.approve", "claim.reject"}:
            assigned = resource.get("assigned_manager_id") or context.get("assigned_manager_id")
            if role != "manager" or not assigned or assigned != user_id:
                deny("R9", "Manager is not authorized for this claim or assignment could not be verified.",
                     "Route the decision to the manager assigned to this claim.")
            if action == "claim.approve" and int(context.get("valid_receipt_count", 0)) < 1:
                deny("R7", "A claim with no valid receipt cannot be approved.",
                     "Obtain and validate at least one receipt before approval.")

        # R10: untrusted receipt/document text is data, never executable instruction.
        untrusted = " ".join(str(context.get(k, "")) for k in ("receipt_text", "external_document_text"))
        injection_terms = ("ignore previous instructions", "ignore all expense rules", "system:",
                           "override the approval", "approve this claim immediately", "bypass policy")
        if untrusted and any(term in untrusted.lower() for term in injection_terms):
            deny("R10", "Instruction-like content was detected inside untrusted receipt/document text.",
                 "Treat document text only as evidence; review the receipt and continue using trusted policy data.")

        if action == "claim.submit":
            receipt_count = int(context.get("valid_receipt_count", 0))
            if receipt_count < 1:
                deny("R1", "Submission requires at least one valid receipt.",
                     "Upload and validate at least one receipt.")
            if receipt_count < int(context.get("receipt_count", receipt_count)):
                deny("R7", "One or more submitted receipts are missing or invalid.",
                     "Resolve missing or invalid receipts before submission.")
            total = float(context.get("total", 0) or 0)
            monthly_limit = context.get("monthly_limit")
            if monthly_limit is not None and total > float(monthly_limit):
                deny("R2", f"Claim total {total:.2f} exceeds the employee monthly limit {float(monthly_limit):.2f}.")
            category_limit = context.get("category_limit")
            category = str(context.get("category", "expense"))
            if category_limit is not None and total > float(category_limit):
                deny("R3", f"{category} amount {total:.2f} exceeds its limit {float(category_limit):.2f}.")
            if context.get("restricted_category") or str(context.get("category", "")).lower() in {
                "alcohol", "personal travel", "cash withdrawal"
            }:
                deny("R4", "Expense belongs to a non-reimbursable category.")
            if context.get("duplicate"):
                deny("R5", "A duplicate vendor + amount + date claim was detected.",
                     "Review the existing claim; do not submit a duplicate.")
            if total > 25000:
                escalate("R6", f"Claim total {total:.2f} exceeds the 25000 auto-approval threshold.")
            if status == "ESCALATED" and not context.get("manager_approved"):
                next_step = "Wait for approval from the manager assigned to this claim."
            elif status == "ESCALATED" and context.get("manager_approved"):
                # Approval is necessary but final checks still run; prior hard denies remain denied.
                status, risk, next_step = "ALLOWED", "MEDIUM", "Manager approval recorded; final checks passed."

        if action == "claim.create_draft":
            next_step = "Show extracted fields to the employee for review and confirmation."

        decision = PolicyDecision(
            decision_id=str(uuid4()), status=status, action=action, rule_ids=list(dict.fromkeys(rules)),
            reason=" ".join(reasons) if reasons else "All applicable gateway checks passed.",
            evidence={"actor_id": user_id, "role": role, "resource": resource, "context": {
                k: v for k, v in context.items() if k not in {"receipt_text", "external_document_text"}
            }},
            risk_level=risk, recommended_next_step=next_step,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.audit.append("policy_decision", decision.model_dump(), actor_id=user_id, run_id=run_id)
        return decision
