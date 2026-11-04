import re
from typing import Optional, List
from app.services.llm_service import interpret_expense_request
from app.services.memory_service import get_employee_memory
from app.services.claim_service import create_draft, submit_claim, triage_pending_claims
from app.utils import new_id, now_iso, dumps, loads
from app.db import get_db
from app.integrations.provider import get_governance

def build_manager_claim_review(manager_id: str, message: str) -> tuple[str, str]:
    """Generates an executive risk review of claims for the manager."""
    triage_pending_claims(manager_id)

    # 1. Check if the manager asked about a specific claim ID
    claim_id_match = re.search(r'(claim-[a-z0-9]+|clm-[0-9]+)', message, re.I)
    if claim_id_match:
        target_id = claim_id_match.group(1).lower()
        with get_db() as db:
            row = db.execute("""
                SELECT c.*, e.name as employee_name
                FROM claims c
                JOIN employees e ON e.id = c.employee_id
                WHERE (lower(c.id)=? OR lower(c.id) LIKE ?) AND c.manager_id=?
            """, (target_id, f"%{target_id}%", manager_id)).fetchone()

        if row:
            cid = row["id"]
            title = row["title"]
            emp_name = row["employee_name"]
            total = float(row["total"] or 0)
            status = row["status"]
            reason = row["decision_reason"] or "Standard evaluation"
            policy = loads(row["policy_json"], {})
            rules_triggered = policy.get("rule_ids", [])

            if status in ("REJECTED", "DECLINED") or "declined" in reason.lower():
                risk_tier = "🔴 HIGH RISK (Declined)"
                recommendation = "Automatically declined by high-risk guardrails. No manager action required."
            elif status == "PENDING_APPROVAL" or total > 25000:
                risk_tier = "🟡 MODERATE RISK (Requires Your Review)"
                recommendation = "Amount exceeds ₹25,000 threshold (Rule R6). Please review receipt validity and business justification. If approved, click '✓ Approve' in the Approval queue."
            else:
                risk_tier = "🟢 LOW RISK (Auto-Approved)"
                recommendation = "Verified compliant with rules R1-R5. Automatically approved by low-risk policy model."

            review = (
                f"🔍 Detailed Claim Review for {cid}:\n\n"
                f"• Title: {title}\n"
                f"• Employee: {emp_name} ({row['employee_id']})\n"
                f"• Amount: ₹{total:,.2f}\n"
                f"• Risk Classification: {risk_tier}\n"
                f"• Current Status: {status}\n"
                f"• Rules Flagged: {', '.join(rules_triggered) if rules_triggered else 'None (Fully compliant)'}\n"
                f"• System Note: {reason}\n\n"
                f"💡 Manager Recommendation:\n{recommendation}"
            )
            return review, "CLAIM_REVIEWED"

    # 2. General Review / Risk Triage of all claims assigned to manager
    with get_db() as db:
        rows = db.execute("""
            SELECT c.*, e.name as employee_name
            FROM claims c
            JOIN employees e ON e.id = c.employee_id
            WHERE c.manager_id = ?
            ORDER BY c.created_at DESC LIMIT 30
        """, (manager_id,)).fetchall()

    moderate = [c for c in rows if c["status"] == "PENDING_APPROVAL"]
    high = [c for c in rows if c["status"] in ("REJECTED", "DECLINED") or "declined" in (c["decision_reason"] or "").lower()]
    low = [c for c in rows if c["status"] in ("APPROVED", "SUBMITTED") and c not in high]

    review_lines = ["📋 Executive Claims & Risk Review:"]

    # Moderate Risk section
    review_lines.append(f"\n🟡 MODERATE RISK — REQUIRES YOUR REVIEW ({len(moderate)}):")
    if moderate:
        for c in moderate[:5]:
            review_lines.append(
                f"• {c['id']}: ₹{float(c['total'] or 0):,.2f} ({c['employee_name']}) — {c['title']}\n"
                f"  └ Trigger: Exceeds ₹25,000 threshold (Rule R6).\n"
                f"  └ Action: Please review receipts & approve or reject in the queue."
            )
        if len(moderate) > 5:
            review_lines.append(f"  └ ... and {len(moderate) - 5} more claims pending review.")
    else:
        review_lines.append("• None. All pending items have been reviewed.")

    # Low Risk section
    review_lines.append(f"\n🟢 LOW RISK — AUTO-APPROVED BY MODEL ({len(low)}):")
    if low:
        for c in low[:3]:
            review_lines.append(
                f"• {c['id']}: ₹{float(c['total'] or 0):,.2f} ({c['employee_name']}) — {c['title']}\n"
                f"  └ Status: Auto-Approved. Clean compliant claim, valid receipt, within limits."
            )
        if len(low) > 3:
            review_lines.append(f"  └ ... and {len(low) - 3} more low-risk claims auto-approved.")
    else:
        review_lines.append("• No low-risk claims recorded yet.")

    # High Risk section
    review_lines.append(f"\n🔴 HIGH RISK — DECLINED BY POLICY ({len(high)}):")
    if high:
        for c in high[:3]:
            reason_snippet = (c["decision_reason"] or "Policy violation").replace("Declined by High-Risk Policy Engine: ", "").replace("High risk model declined claim: ", "")
            review_lines.append(
                f"• {c['id']}: ₹{float(c['total'] or 0):,.2f} ({c['employee_name']}) — {c['title']}\n"
                f"  └ Reason: {reason_snippet}"
            )
        if len(high) > 3:
            review_lines.append(f"  └ ... and {len(high) - 3} more high-risk claims declined.")
    else:
        review_lines.append("• None. No high-risk violations detected.")

    review_lines.append(
        f"\n📊 Summary: {len(moderate)} Pending Review · {len(low)} Auto-Approved · {len(high)} Declined\n"
        "💡 You can approve or reject moderate risk claims directly in the Approval Queue."
    )

    return "\n".join(review_lines), "REVIEW_APPROVAL_QUEUE" if moderate else "NO_ACTION_REQUIRED"

def generate_agent_response(message: str, memory: dict, intent: dict) -> tuple[str, str]:
    """Generates an intelligent contextual response and recommended next action."""
    msg = message.lower()
    role = memory.get("role", "employee").lower()
    name = memory.get("name", "there")

    # Manager queries
    if role == "manager":
        # Check if asking for review, triage, risk assessment, or summarizing claims
        if any(w in msg for w in ["review", "summarize", "pending", "queue", "approvals", "awaiting", "triage", "risk", "status", "auto-approved", "auto approved", "declined", "how many", "high risk", "low risk", "moderate", "overview", "claims", "portfolio"]):
            return build_manager_claim_review(memory["employee_id"], message)

        if any(w in msg for w in ["25000", "25,000", "threshold", "approval rule"]):
            return (
                "Under Rule R6: Claims with a total exceeding ₹25,000 require explicit manager approval. "
                "The agent escalates these claims to PENDING_APPROVAL status (Moderate Risk). Once approved, the manager "
                "finalizes submission to the ERP.",
                "POLICY_EXPLAINED"
            )

        if any(w in msg for w in ["check", "before approving", "criteria", "verify"]):
            return (
                "Before approving an expense claim, check:\n"
                "1. Valid Receipts (R1 & R7): Ensure at least one legitimate receipt is attached.\n"
                "2. Meals Limit (R3): Individual meal expenses must not exceed ₹5,000.\n"
                "3. Restricted Items (R4): Alcohol, personal travel, and cash withdrawals are prohibited.\n"
                "4. Business Relevance: Purpose aligns with approved company activities.",
                "POLICY_EXPLAINED"
            )

    # Policy questions (Employee & Manager)
    if any(w in msg for w in ["meal", "food", "lunch", "dinner"]):
        return (
            "Under Policy Rule R3: Meal expenses are capped at ₹5,000 per claim. "
            "Any claim exceeding this threshold is classified as High Risk and blocked automatically by the policy gateway.",
            "POLICY_EXPLAINED"
        )

    if any(w in msg for w in ["receipt", "receipts", "file", "attach", "upload"]):
        return (
            "Under Policy Rules R1 & R7: Every expense claim requires at least one valid receipt "
            "(PDF, PNG, or JPG up to 10MB). Claims submitted without receipts are High Risk, blocked from submission, "
            "and cannot be approved by any manager.",
            "UPLOAD_RECEIPTS"
        )

    if any(w in msg for w in ["alcohol", "beer", "wine", "cash", "personal"]):
        return (
            "Under Policy Rule R4: Expenses for alcohol, personal travel, and cash withdrawals are strictly "
            "restricted and non-reimbursable. High-risk policy guardrails automatically decline claims in these categories.",
            "POLICY_EXPLAINED"
        )

    if any(w in msg for w in ["policy", "rules", "how do i submit", "guideline", "limit"]):
        limit = memory.get("monthly_limit", 100000)
        return (
            f"Here is your Sentra Expense Policy Summary:\n"
            f"• Monthly Limit (R2): ₹{float(limit):,.0f}\n"
            f"• Meal Limit (R3): Max ₹5,000 per meal\n"
            f"• Receipts (R1/R7): Required for all submissions\n"
            f"• Risk Tiers:\n"
            f"  - 🟢 Low Risk (<= ₹25k, compliant): Auto-Approved to ERP\n"
            f"  - 🟡 Moderate Risk (> ₹25k): Routed for Manager Review (R6)\n"
            f"  - 🔴 High Risk (Policy violations, alcohol, duplicate): Automatically Declined\n"
            f"To submit an expense, attach receipts in the chat or use the '+ New claim' modal.",
            "POLICY_EXPLAINED"
        )

    if any(w in msg for w in ["status", "my claims", "history", "recent"]):
        claims = memory.get("recent_claims", [])
        if claims:
            res = "Here are your recent expense claims:\n"
            for c in claims[:3]:
                res += f"• {c.get('title')}: ₹{float(c.get('total', 0)):,.0f} ({c.get('status')})\n"
            return res, "VIEW_CLAIMS"
        return "You have not submitted any claims recently.", "CREATE_EXPENSE_DRAFT"

    # Specific expense intent detected without receipt
    if intent.get("amount"):
        amt = intent["amount"]
        cat = intent.get("category", "expense")
        vendor_txt = f" from {intent['vendor']}" if intent.get("vendor") else ""
        return (
            f"I extracted your expense: {cat.title()}{vendor_txt} of ₹{amt:,.2f}. "
            "To complete submission, please attach the receipt (📎) here in chat. "
            "The low-risk engine will auto-approve compliant claims up to ₹25,000, "
            "or route to your manager if over threshold.",
            "UPLOAD_RECEIPTS_AND_CREATE_DRAFT"
        )

    return (
        f"Hello {name.split()[0]}! I'm Sentra AI, your governed expense companion. "
        "You can attach receipts here to auto-draft and submit claims through policy governance, "
        "or ask questions about expense policies.",
        "UPLOAD_RECEIPTS_AND_CREATE_DRAFT"
    )

def run_expense_agent(
    employee_id: str,
    message: str,
    receipt_ids: Optional[List[str]] = None,
    auto_submit: bool = True
) -> dict:
    run_id = new_id("run")
    trace = []
    memory = get_employee_memory(employee_id)
    if not memory:
        raise ValueError("Employee not found")

    intent = interpret_expense_request(message)
    target_receipts = []

    # Check for provided receipts or unlinked receipts
    with get_db() as db:
        if receipt_ids:
            for rid in receipt_ids:
                row = db.execute("SELECT * FROM receipts WHERE id=? AND employee_id=?", (rid, employee_id)).fetchone()
                if row:
                    target_receipts.append(dict(row))
        else:
            wants_submit = any(k in message.lower() for k in ["submit", "claim", "receipt", "draft", "expense", "bill", "invoice", "total", "amount", "rs", "inr"]) or intent.get("amount") is not None
            if wants_submit:
                all_rcpts = db.execute("SELECT * FROM receipts WHERE employee_id=? ORDER BY created_at DESC LIMIT 5", (employee_id,)).fetchall()
                claim_rows = db.execute("SELECT items_json FROM claims WHERE employee_id=?", (employee_id,)).fetchall()
                claimed_rids = set()
                for cr in claim_rows:
                    for it in loads(cr["items_json"], []):
                        if it.get("receipt_id"):
                            claimed_rids.add(it["receipt_id"])
                for r in all_rcpts:
                    if r["id"] not in claimed_rids:
                        target_receipts.append(dict(r))
                        break

    # If receipts present, automate draft creation & policy-governed submission!
    if target_receipts:
        items = []
        for r in target_receipts:
            rcpt_amount = r.get("amount")
            final_amount = rcpt_amount if rcpt_amount is not None else intent.get("amount")

            if final_amount is None:
                vendor_txt = r.get("vendor") or "your uploaded bill"
                response_text = (
                    f"I scanned {vendor_txt}, but could not clearly read the total bill amount from the document. "
                    "Please state the total amount (e.g. 'The total bill is Rs. 1450') so I can process and evaluate your claim."
                )
                return {
                    "run_id": run_id,
                    "employee_id": employee_id,
                    "intent": intent,
                    "memory": memory,
                    "claim": None,
                    "policy": None,
                    "next_action": "NEED_AMOUNT_CONFIRMATION",
                    "message": response_text,
                    "response": response_text
                }

            items.append({
                "receipt_id": r["id"],
                "vendor": r.get("vendor") or intent.get("vendor") or "Vendor",
                "date": r.get("expense_date") or now_iso()[:10],
                "amount": float(final_amount),
                "category": r.get("category") or intent.get("category") or "other",
                "description": intent.get("purpose") or "Automated expense claim"
            })

        first = items[0]
        title = intent.get("title")
        if not title or title == message[:80].strip():
            title = f"{first['vendor']} - {first['category'].title()}"

        purpose = intent.get("purpose") or f"Automated claim for {first['vendor']}"

        # 1. Create draft claim
        draft = create_draft(employee_id, title, purpose, items)
        claim_id = draft["id"]
        trace.append({"step": "DRAFT_CREATED", "detail": f"Draft claim {claim_id} created automatically", "data": draft, "timestamp": now_iso()})
        get_governance().record_event("DRAFT_CREATED", f"Agent created draft {claim_id}", actor_id=employee_id, claim_id=claim_id, payload=draft)

        claim = draft
        policy = {}
        next_action = "DRAFT_CREATED"

        # 2. Automatically submit through risk & policy evaluation
        if auto_submit:
            sub_res = submit_claim(claim_id, employee_id, confirmation=True)
            claim = sub_res.get("claim") or draft
            policy = sub_res.get("policy") or {}
            status = claim.get("status")
            risk_tier = sub_res.get("risk_level", "LOW")

            if status in ("APPROVED", "SUBMITTED") and risk_tier == "LOW":
                response_text = (
                    f"⚡ Low Risk Claim Auto-Approved:\n"
                    f"Created and approved claim '{claim['title']}' for ₹{claim['total']:,.2f} (ID: {claim['id']}).\n"
                    f"The low-risk model verified all policy rules (R1–R9) with valid receipts. The claim is approved and submitted to the ERP."
                )
                next_action = "CLAIM_AUTO_APPROVED"
            elif status == "PENDING_APPROVAL":
                response_text = (
                    f"⚡ Moderate Risk Claim Routed for Manager Review:\n"
                    f"Created claim '{claim['title']}' for ₹{claim['total']:,.2f} (ID: {claim['id']}).\n"
                    f"Under Rule R6: Amount exceeds the ₹25,000 threshold. The claim has been automatically sent to your manager for approval."
                )
                next_action = "CLAIM_ESCALATED_FOR_APPROVAL"
            else:
                reasons = sub_res.get("message") or "; ".join(policy.get("reasons", ["Policy violation detected"]))
                response_text = (
                    f"🔴 High Risk Claim Automatically Declined:\n"
                    f"Claim '{claim['title']}' for ₹{claim['total']:,.2f} (ID: {claim['id']}) violated policy rules.\n"
                    f"Reason: {reasons}."
                )
                next_action = "CLAIM_DECLINED"

            trace.append({"step": next_action, "detail": response_text, "data": policy, "timestamp": now_iso()})
        else:
            response_text = f"Draft claim {claim_id} prepared for ₹{draft['total']:,.2f}. Review and submit when ready."
            next_action = "DRAFT_READY"

        with get_db() as db:
            db.execute(
                "INSERT INTO agent_runs VALUES (?,?,?,?,?,?)",
                (run_id, employee_id, claim_id, next_action, dumps(trace), now_iso())
            )

        return {
            "run_id": run_id,
            "employee_id": employee_id,
            "intent": intent,
            "memory": memory,
            "claim": claim,
            "policy": policy,
            "next_action": next_action,
            "message": response_text,
            "response": response_text
        }

    # Standard conversational inquiry without receipt
    response_text, next_action = generate_agent_response(message, memory, intent)

    for event, detail, payload in [
        ("MEMORY_LOOKUP", "Loaded employee profile and recent claims", {"recent_claim_count": len(memory.get("recent_claims", []))}),
        ("INTENT_PARSED", "Parsed expense request and generated governed response", {"intent": intent, "action": next_action}),
    ]:
        trace.append({"step": event, "detail": detail, "data": payload, "timestamp": now_iso()})
        get_governance().record_event(event, detail, actor_id=employee_id, run_id=run_id, payload=payload)

    with get_db() as db:
        db.execute(
            "INSERT INTO agent_runs VALUES (?,?,?,?,?,?)",
            (run_id, employee_id, None, next_action, dumps(trace), now_iso())
        )

    return {
        "run_id": run_id,
        "employee_id": employee_id,
        "intent": intent,
        "memory": memory,
        "claim": None,
        "policy": None,
        "next_action": next_action,
        "message": response_text,
        "response": response_text
    }
