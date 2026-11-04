from app.db import get_db
from app.utils import new_id, now_iso, dumps, loads
from app.services.policy_rules import evaluate_claim_rules, check_manager_assignment
from app.integrations.provider import get_governance
from app.schemas import ToolCall

def create_draft(employee_id, title, purpose, items, cost_center=None):
    with get_db() as db:
        employee = db.execute("SELECT * FROM employees WHERE id=?", (employee_id,)).fetchone()
        if not employee:
            raise ValueError("Employee not found")
        normalized = []
        for item in items:
            item = dict(item)
            if item.get("receipt_id"):
                receipt = db.execute("SELECT * FROM receipts WHERE id=? AND employee_id=?", (item["receipt_id"], employee_id)).fetchone()
                if not receipt:
                    raise ValueError("Receipt not found or not owned by employee")
                item["vendor"] = item.get("vendor") or receipt["vendor"]
                item["date"] = item.get("date") or receipt["expense_date"]
                item["amount"] = item.get("amount") or receipt["amount"]
                item["category"] = item.get("category") or receipt["category"]
            normalized.append(item)
        total = round(sum(float(x["amount"]) for x in normalized), 2)
        cid = new_id("claim")
        now = now_iso()
        db.execute("""INSERT INTO claims
          (id,employee_id,manager_id,title,purpose,cost_center,status,total,currency,items_json,policy_json,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (cid, employee_id, employee["manager_id"], title, purpose, cost_center or employee["cost_center"],
           "DRAFT", total, "INR", dumps(normalized), dumps([]), now, now))
        row = db.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
        result = evaluate_claim_rules(db, row, normalized)
        db.execute("UPDATE claims SET policy_json=? WHERE id=?", (dumps(result), cid))
    get_governance().record_event("DRAFT_CREATED", f"Draft claim {cid} created", actor_id=employee_id, claim_id=cid, payload={"total": total})
    return get_claim(cid)

def get_claim(cid):
    with get_db() as db:
        row = db.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["items"] = loads(item.pop("items_json"), [])
    policy = loads(item.pop("policy_json"), {})
    item["policy"] = policy
    
    # Standardize risk_level
    if isinstance(policy, dict) and policy.get("risk_level"):
        item["risk_level"] = policy["risk_level"]
    elif item.get("status") in ("REJECTED", "BLOCKED"):
        item["risk_level"] = "HIGH"
    elif float(item.get("total", 0)) > 25000:
        item["risk_level"] = "MEDIUM"
    else:
        item["risk_level"] = "LOW"

    return item

def submit_claim(cid, employee_id, confirmation=True):
    if not confirmation:
        raise ValueError("Explicit employee confirmation is required")
    with get_db() as db:
        row = db.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
        if not row:
            raise ValueError("Claim not found")
        if row["employee_id"] != employee_id:
            raise PermissionError("R8: claim belongs to another employee")
        if row["status"] not in ("DRAFT", "NEEDS_CHANGES", "PENDING_APPROVAL"):
            raise ValueError(f"Cannot submit claim in status {row['status']}")
        items = loads(row["items_json"], [])
        rules = evaluate_claim_rules(db, row, items)
        db.execute("UPDATE claims SET policy_json=?,updated_at=? WHERE id=?", (dumps(rules), now_iso(), cid))

    # 1. High Risk Check: Rule violations automatically decline
    if rules["decision"] == "DENIED":
        reason_text = "High Risk - Declined by Policy Engine: " + "; ".join(rules["reasons"])
        with get_db() as db:
            db.execute("UPDATE claims SET status='REJECTED',decision_reason=?,updated_at=? WHERE id=?",
                       (reason_text, now_iso(), cid))
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)",
                       (new_id("appr"), cid, row["manager_id"] or "SYSTEM", "REJECTED", reason_text, now_iso(), now_iso()))
        get_governance().record_event("CLAIM_DECLINED_HIGH_RISK", reason_text, actor_id=employee_id, claim_id=cid, payload=rules)
        return {"claim": get_claim(cid), "policy": rules, "message": reason_text, "action": "DECLINED", "risk_level": "HIGH"}

    # Central policy gateway authorization
    gateway = get_governance().authorize_tool_call(ToolCall(
        actor_id=employee_id,
        tool_name="submit_claim",
        action="submit",
        resource_owner_id=employee_id,
        claim_id=cid,
        amount=row["total"]
    ))

    if gateway.decision == "DENIED":
        reason_text = "High Risk - Declined by Security Gateway: " + "; ".join(gateway.reasons)
        with get_db() as db:
            db.execute("UPDATE claims SET status='REJECTED',decision_reason=?,updated_at=? WHERE id=?",
                       (reason_text, now_iso(), cid))
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)",
                       (new_id("appr"), cid, row["manager_id"] or "SYSTEM", "REJECTED", reason_text, now_iso(), now_iso()))
        get_governance().record_event("CLAIM_DECLINED_HIGH_RISK", reason_text, actor_id=employee_id, claim_id=cid, payload=gateway.model_dump())
        return {"claim": get_claim(cid), "policy": gateway.model_dump(), "message": reason_text, "action": "DECLINED", "risk_level": "HIGH"}

    # 2. Moderate Risk Check: Claims exceeding threshold require Manager Review
    if rules["decision"] == "ESCALATED" or gateway.decision == "ESCALATED":
        reason_text = "Moderate Risk: Escalated for Manager Review (" + "; ".join(rules["reasons"]) + ")"
        with get_db() as db:
            db.execute("UPDATE claims SET status='PENDING_APPROVAL',decision_reason=?,updated_at=? WHERE id=?",
                       (reason_text, now_iso(), cid))
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)",
                       (new_id("appr"), cid, row["manager_id"], "PENDING", None, now_iso(), None))
        get_governance().record_event("APPROVAL_REQUESTED_MODERATE_RISK", "Claim routed for manager review", actor_id=employee_id, claim_id=cid, payload=rules)
        return {"claim": get_claim(cid), "policy": rules, "message": "Moderate risk claim routed to manager for explicit review", "action": "NEEDS_REVIEW", "risk_level": "MEDIUM"}

    # 3. Low Risk Check: Clean, compliant claim is Auto-Approved by low risk model!
    reason_text = "Auto-approved: Low risk model verified all policy rules (R1-R9) passed."
    now = now_iso()
    with get_db() as db:
        db.execute("UPDATE claims SET status='APPROVED',submitted_at=?,decision_reason=?,updated_at=? WHERE id=?",
                   (now, reason_text, now, cid))
        db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)",
                   (new_id("appr"), cid, row["manager_id"] or "SYSTEM", "APPROVED", reason_text, now, now))
    get_governance().record_event("CLAIM_AUTO_APPROVED_LOW_RISK", reason_text, actor_id=employee_id, claim_id=cid, payload=rules)
    return {"claim": get_claim(cid), "policy": rules, "message": reason_text, "action": "AUTO_APPROVED", "risk_level": "LOW"}

def triage_pending_claims(manager_id: str):
    """Automatically triages claims assigned to this manager by risk model."""
    with get_db() as db:
        rows = db.execute("SELECT * FROM claims WHERE manager_id=? AND status='PENDING_APPROVAL'", (manager_id,)).fetchall()
        for row in rows:
            cid = row["id"]
            items = loads(row["items_json"], [])
            rules = evaluate_claim_rules(db, row, items)
            if rules["risk_level"] == "LOW":
                now = now_iso()
                reason = "Auto-approved: Low risk model verified all policy rules (R1-R9)."
                db.execute("UPDATE claims SET status='APPROVED',submitted_at=?,decision_reason=?,updated_at=? WHERE id=?", (now, reason, now, cid))
                db.execute("UPDATE approvals SET status='APPROVED',reason=?,decided_at=? WHERE claim_id=? AND status='PENDING'", (reason, now, cid))
            elif rules["risk_level"] == "HIGH":
                now = now_iso()
                reason = "High risk model declined claim: " + "; ".join(rules["reasons"])
                db.execute("UPDATE claims SET status='REJECTED',decision_reason=?,updated_at=? WHERE id=?", (reason, now, cid))
                db.execute("UPDATE approvals SET status='REJECTED',reason=?,decided_at=? WHERE claim_id=? AND status='PENDING'", (reason, now, cid))

def manager_decision(cid, manager_id, approve, reason=""):
    with get_db() as db:
        row = db.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
        if not row:
            raise ValueError("Claim not found")

        access = check_manager_assignment(manager_id, row)
        if access["decision"] == "DENIED":
            raise PermissionError(access["reasons"][0])

        if row["status"] not in ("PENDING_APPROVAL", "DRAFT"):
            raise ValueError("Claim is not awaiting approval")

        items = loads(row["items_json"], [])
        rules = evaluate_claim_rules(db, row, items)

        if approve and (
            rules["decision"] == "DENIED"
            or not any(x.get("receipt_id") for x in items)
        ):
            raise ValueError(
                "R7: claim with missing receipt or blocked rule cannot be approved"
            )

    gateway = get_governance().authorize_tool_call(
        ToolCall(
            actor_id=manager_id,
            tool_name="manager_decision",
            action="approve" if approve else "reject",
            claim_id=cid,
        )
    )

    if gateway.decision != "ALLOWED":
        raise PermissionError(
            f"Governance {gateway.decision}: {'; '.join(gateway.reasons)}"
        )

    status = "APPROVED" if approve else "REJECTED"
    decision_text = f"Manager {'approved' if approve else 'declined'}: {reason}".strip()

    with get_db() as db:
        db.execute(
            "UPDATE claims SET status=?,decision_reason=?,updated_at=? WHERE id=?",
            (status, decision_text, now_iso(), cid),
        )
        db.execute(
            """UPDATE approvals SET status=?,reason=?,decided_at=?
               WHERE claim_id=? AND status='PENDING'""",
            (status, decision_text, now_iso(), cid),
        )

    get_governance().record_event(
        "MANAGER_APPROVED" if approve else "MANAGER_REJECTED",
        f"Manager {status.lower()} claim",
        actor_id=manager_id,
        claim_id=cid,
        payload={"reason": reason},
    )

    return get_claim(cid)

def finalize_approved_claim(cid, manager_id):
    with get_db() as db:
        row = db.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
        if not row:
            raise ValueError("Claim not found")

        if row["status"] != "APPROVED":
            raise ValueError("Claim must be manager-approved first")

        if row["manager_id"] != manager_id and row["manager_id"] is not None:
            raise PermissionError("R9: unauthorized manager")

        rules = evaluate_claim_rules(
            db, row, loads(row["items_json"], [])
        )

        if rules["decision"] == "DENIED":
            raise ValueError("Final policy check failed")

    gateway = get_governance().authorize_tool_call(
        ToolCall(
            actor_id=manager_id,
            tool_name="finalize_approved_claim",
            action="finalize",
            claim_id=cid,
        )
    )

    if gateway.decision != "ALLOWED":
        raise PermissionError(
            f"Governance {gateway.decision}: {'; '.join(gateway.reasons)}"
        )

    with get_db() as db:
        db.execute(
            """UPDATE claims SET status='SUBMITTED',
               submitted_at=?,updated_at=? WHERE id=?""",
            (now_iso(), now_iso(), cid),
        )

    get_governance().record_event(
        "CLAIM_SUBMITTED",
        "Approved claim submitted to mock ERP",
        actor_id=manager_id,
        claim_id=cid,
        payload=rules,
    )

    return get_claim(cid)
