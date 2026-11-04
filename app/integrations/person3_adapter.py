
"""Person 3 governance adapter for Person 1's SentraAI backend.

Person 1 remains authoritative for R1-R9 domain checks. Person 3's gateway
adds centralized action interception and R10 untrusted-document detection.
"""

from __future__ import annotations

from typing import Any

from app.db import get_db
from app.schemas import PolicyDecision, ToolCall
from app.services.policy_rules import (
    evaluate_claim_rules,
    check_employee_scope,
    check_manager_assignment,
)
from app.utils import loads, dumps, now_iso, new_id
from governance.runtime import audit_store, gateway, redteam


class Person3GovernanceAdapter:

    def _deny(self, rule_id: str, reason: str) -> PolicyDecision:
        result = PolicyDecision(
            decision="DENIED",
            rule_ids=[rule_id],
            reasons=[reason],
            risk_level="HIGH",
            evidence=[],
        )

        audit_store.append(
            "policy_decision",
            {
                "status": "DENIED",
                "rule_ids": [rule_id],
                "reason": reason,
            },
        )
        return result

    def _domain_decision(
        self,
        result: dict[str, Any],
        *,
        actor_id: str,
        action: str,
        claim_id: str | None,
    ) -> PolicyDecision:

        decision = PolicyDecision(**result)

        audit_store.append(
            "policy_decision",
            {
                "status": decision.decision,
                "action": action,
                "rule_ids": decision.rule_ids,
                "reasons": decision.reasons,
                "claim_id": claim_id,
            },
            actor_id=actor_id,
        )

        return decision

    def _claim_context(
        self,
        claim_id: str | None,
    ) -> dict[str, Any] | None:

        if not claim_id:
            return None

        with get_db() as db:
            claim = db.execute(
                "SELECT * FROM claims WHERE id=?",
                (claim_id,),
            ).fetchone()

            if not claim:
                return None

            items = loads(claim["items_json"], [])
            receipts = []

            for item in items:
                rid = item.get("receipt_id")

                if rid:
                    receipt = db.execute(
                        """
                        SELECT * FROM receipts
                        WHERE id=? AND employee_id=?
                        """,
                        (rid, claim["employee_id"]),
                    ).fetchone()

                    if receipt:
                        receipts.append(dict(receipt))

            return {
                "claim": dict(claim),
                "items": items,
                "receipts": receipts,
            }

    def authorize_tool_call(self, call: ToolCall) -> PolicyDecision:

        tool = call.tool_name.strip().lower()
        action = call.action.strip().lower()

        data = self._claim_context(call.claim_id)

        # Resolve trusted role from the backend database.
        with get_db() as db:
            actor_row = db.execute(
                "SELECT * FROM employees WHERE id=?",
                (call.actor_id,),
            ).fetchone()

        role = str(actor_row["role"]).lower() if actor_row else "employee"

        actor = {
            "user_id": call.actor_id,
            "role": role,
        }

        resource: dict[str, Any] = {}
        context: dict[str, Any] = {}

        # Load claim and receipt context.
        if data:
            claim = data["claim"]
            items = data["items"]
            receipts = data["receipts"]

            resource = {
                "owner_id": claim["employee_id"],
                "employee_id": claim["employee_id"],
                "assigned_manager_id": claim["manager_id"],
                "claim_id": claim["id"],
            }

            receipt_text = "\n".join(
                str(receipt.get("extracted_text") or "")
                for receipt in receipts
            )

            context = {
                "total": float(claim["total"] or 0),
                "valid_receipt_count": len(receipts),
                "receipt_count": len(items),
                "receipt_text": receipt_text,
            }

        # ==================================================
        # SUBMISSION / MANAGER DECISION / FINALIZATION
        # ==================================================

        if tool in {
            "submit_claim",
            "finalize_approved_claim",
            "manager_decision",
        }:

            if not data:
                return self._deny(
                    "R0",
                    "Claim does not exist or could not be loaded.",
                )

            claim = data["claim"]
            items = data["items"]

            with get_db() as db:
                fresh_claim = db.execute(
                    "SELECT * FROM claims WHERE id=?",
                    (call.claim_id,),
                ).fetchone()

                if not fresh_claim:
                    return self._deny(
                        "R0",
                        "Claim does not exist or could not be loaded.",
                    )

                rules = evaluate_claim_rules(
                    db,
                    fresh_claim,
                    items,
                )

            # Employee submission.
            if tool == "submit_claim":

                scope = check_employee_scope(
                    call.actor_id,
                    claim["employee_id"],
                )

                if scope["decision"] == "DENIED":
                    return self._domain_decision(
                        scope,
                        actor_id=call.actor_id,
                        action="claim.submit",
                        claim_id=call.claim_id,
                    )

                action_name = "claim.submit"

                if rules["decision"] == "DENIED":
                    return self._domain_decision(
                        rules,
                        actor_id=call.actor_id,
                        action=action_name,
                        claim_id=call.claim_id,
                    )

            # Manager approval or rejection.
            elif tool == "manager_decision":

                assignment = check_manager_assignment(
                    call.actor_id,
                    claim,
                )

                if assignment["decision"] == "DENIED":
                    return self._domain_decision(
                        assignment,
                        actor_id=call.actor_id,
                        action=(
                            "claim.approve"
                            if action in {"approve", "approved"}
                            else "claim.reject"
                        ),
                        claim_id=call.claim_id,
                    )

                is_approve = action in {"approve", "approved"}

                action_name = (
                    "claim.approve"
                    if is_approve
                    else "claim.reject"
                )

                if is_approve and rules["decision"] == "DENIED":
                    return self._domain_decision(
                        rules,
                        actor_id=call.actor_id,
                        action=action_name,
                        claim_id=call.claim_id,
                    )

            # Finalize an approved claim.
            else:

                assignment = check_manager_assignment(
                    call.actor_id,
                    claim,
                )

                if assignment["decision"] == "DENIED":
                    return self._domain_decision(
                        assignment,
                        actor_id=call.actor_id,
                        action="claim.finalize",
                        claim_id=call.claim_id,
                    )

                if claim["status"] != "APPROVED":
                    return self._deny(
                        "R9",
                        "Only an approved claim can be finalized by its assigned manager.",
                    )

                if rules["decision"] == "DENIED":
                    return self._domain_decision(
                        rules,
                        actor_id=call.actor_id,
                        action="claim.finalize",
                        claim_id=call.claim_id,
                    )

                action_name = "claim.submit"
                context["manager_approved"] = True

        # ==================================================
        # CLAIM READ ACCESS
        # ==================================================

        elif tool in {"get_claim", "claim_detail"}:

            if not data:
                return self._deny(
                    "R0",
                    "Claim does not exist or could not be loaded.",
                )

            claim = data["claim"]

            # Employees can read only their own claims.
            if role == "employee":

                scope = check_employee_scope(
                    call.actor_id,
                    claim["employee_id"],
                )

                if scope["decision"] == "DENIED":
                    return self._domain_decision(
                        scope,
                        actor_id=call.actor_id,
                        action="claim.read",
                        claim_id=call.claim_id,
                    )

            # Managers can read only claims assigned to them.
            elif role == "manager":

                assignment = check_manager_assignment(
                    call.actor_id,
                    claim,
                )

                if assignment["decision"] == "DENIED":
                    return self._domain_decision(
                        assignment,
                        actor_id=call.actor_id,
                        action="claim.read",
                        claim_id=call.claim_id,
                    )

            else:
                return self._deny(
                    "R8",
                    "This role is not authorized to read this claim.",
                )

            # Both authorized roles reach this assignment.
            action_name = "claim.read"

            resource = {
                "owner_id": claim["employee_id"],
                "assigned_manager_id": claim["manager_id"],
                "claim_id": call.claim_id,
            }

        # ==================================================
        # DRAFT CREATION / UNSUPPORTED ACTIONS
        # ==================================================

        else:

            if tool in {"create_draft", "draft_claim"}:

                action_name = "claim.create_draft"

                resource = {
                    "owner_id": call.resource_owner_id or call.actor_id,
                }

            else:
                action_name = "unsupported"

        # ==================================================
        # CENTRAL GOVERNANCE GATEWAY
        # ==================================================

        decision = gateway.evaluate(
            action_name,
            actor,
            resource,
            context,
        )

        result = PolicyDecision(
            decision=decision.status,
            rule_ids=decision.rule_ids,
            reasons=[decision.reason],
            risk_level=decision.risk_level,
            evidence=[decision.evidence],
        )

        # Preserve Person 1's R6 escalation decision.
        if tool == "submit_claim" and data:

            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM claims WHERE id=?",
                    (call.claim_id,),
                ).fetchone()

                policy = evaluate_claim_rules(
                    db,
                    row,
                    data["items"],
                )

            if (
                policy["decision"] == "ESCALATED"
                and result.decision == "ALLOWED"
            ):
                result.decision = "ESCALATED"

                result.rule_ids = list(
                    dict.fromkeys(
                        result.rule_ids + policy["rule_ids"]
                    )
                )

                result.reasons = policy["reasons"]
                result.risk_level = policy["risk_level"]

        return result

    # ======================================================
    # AUDIT EVENT RECORDING
    # ======================================================

    def record_event(
        self,
        event_type: str,
        message: str,
        *,
        actor_id: str = "",
        run_id: str | None = None,
        claim_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:

        body = {
            "message": message,
            "claim_id": claim_id,
            **(payload or {}),
        }

        audit_store.append(
            event_type.lower(),
            body,
            actor_id=actor_id or None,
            run_id=run_id,
        )

        # Preserve Person 1's legacy event stream.
        with get_db() as db:
            db.execute(
                """
                INSERT INTO audit_events
                (
                    id,
                    run_id,
                    claim_id,
                    actor_id,
                    event_type,
                    message,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("evt"),
                    run_id,
                    claim_id,
                    actor_id,
                    event_type,
                    message,
                    dumps(payload or {}),
                    now_iso(),
                ),
            )

    # ======================================================
    # GOVERNANCE METRICS
    # ======================================================

    def metrics(self) -> dict[str, Any]:

        from governance.metrics import build_metrics

        result = build_metrics(audit_store)

        with get_db() as db:
            result.update(
                {
                    "total_claims": db.execute(
                        "SELECT COUNT(*) FROM claims"
                    ).fetchone()[0],

                    "submitted_claims": db.execute(
                        "SELECT COUNT(*) FROM claims WHERE status='SUBMITTED'"
                    ).fetchone()[0],

                    "pending_approvals": db.execute(
                        "SELECT COUNT(*) FROM claims WHERE status='PENDING_APPROVAL'"
                    ).fetchone()[0],
                }
            )

        return result

    # ======================================================
    # RED TEAM TESTING
    # ======================================================

    def run_redteam(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        attack_type = str(
            payload.get("attack_type") or ""
        ).lower()

        aliases = {
            "prompt_injection": "prompt_injection",
            "poisoned_receipt": "poisoned_receipt",
            "authority_impersonation": "authority_impersonation",
            "data_exfiltration": "data_exfiltration",
            "policy_bypass": "policy_bypass",
        }

        scenario_id = aliases.get(
            attack_type,
            attack_type or None,
        )

        actor_id = payload.get("employee_id") or "JUDGE"

        with get_db() as db:
            row = db.execute(
                "SELECT role FROM employees WHERE id=?",
                (actor_id,),
            ).fetchone()

        actor = {
            "user_id": actor_id,
            "role": row["role"] if row else "admin",
        }

        return redteam.run(
            scenario_id=scenario_id,
            prompt=payload.get("prompt"),
            receipt_text=payload.get("receipt_text"),
            actor=actor,
        )
