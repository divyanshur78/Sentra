"""Person 1 deterministic R1-R9 domain rules. Person 3 owns gateway interception and R10."""
from app.utils import loads

CATEGORY_LIMITS = {"meal": 5000.0}
RESTRICTED = {"alcohol", "personal_travel", "cash_withdrawal"}
RULES = [
 {"id":"R1","name":"Receipt required","description":"Claim must contain at least one valid receipt.","outcome":"Block submission if missing"},
 {"id":"R2","name":"Monthly employee limit","description":"Claim total plus current-month submitted/pending spend must not exceed employee monthly limit.","outcome":"Block"},
 {"id":"R3","name":"Category limits","description":"Category-specific limits apply; meal limit is ₹5,000.","outcome":"Block"},
 {"id":"R4","name":"Restricted categories","description":"Alcohol, personal travel, and cash withdrawals are non-reimbursable.","outcome":"Block"},
 {"id":"R5","name":"Duplicate claim","description":"Duplicate vendor + amount + date claims are not allowed.","outcome":"Block"},
 {"id":"R6","name":"Manager approval threshold","description":"Claims above ₹25,000 require manager approval.","outcome":"Escalate"},
 {"id":"R7","name":"Missing receipt cannot be approved","description":"Claims without receipts cannot be approved.","outcome":"Block"},
 {"id":"R8","name":"Employee data scope","description":"Employees can access only their own claims and profile.","outcome":"Deny cross-user access"},
 {"id":"R9","name":"Manager assignment","description":"Managers can approve only claims assigned to them.","outcome":"Deny unauthorized approval"}
]

def evaluate_claim_rules(db, claim, items):
    blocked, escalated, reasons, evidence = [], [], [], []
    employee=db.execute("SELECT * FROM employees WHERE id=?",(claim["employee_id"],)).fetchone()
    if not any(item.get("receipt_id") for item in items):
        blocked.append("R1"); reasons.append("At least one valid receipt is required.")
    if employee:
        spend=db.execute("""SELECT COALESCE(SUM(total),0) FROM claims
          WHERE employee_id=? AND status IN ('SUBMITTED','PENDING_APPROVAL')
          AND substr(created_at,1,7)=substr(?,1,7) AND id<>?""",
          (claim["employee_id"],claim["created_at"],claim["id"])).fetchone()[0]
        if spend+float(claim["total"])>float(employee["monthly_limit"]):
            blocked.append("R2"); reasons.append(f"Monthly limit exceeded: ₹{spend+float(claim['total']):.2f} > ₹{employee['monthly_limit']:.2f}.")
    for item in items:
        category=(item.get("category") or "").lower().replace(" ","_")
        amount=float(item.get("amount") or 0)
        if category in RESTRICTED:
            blocked.append("R4"); reasons.append(f"Restricted category '{category}' is non-reimbursable.")
            evidence.append({"vendor":item.get("vendor"),"category":category,"amount":amount})
        limit=CATEGORY_LIMITS.get(category)
        if limit and amount>limit:
            blocked.append("R3"); reasons.append(f"Meal expense ₹{amount:.2f} exceeds ₹{limit:.2f} limit.")
            evidence.append({"vendor":item.get("vendor"),"category":category,"amount":amount,"limit":limit})
        if item.get("vendor") and item.get("date"):
            duplicate=db.execute("""SELECT c.id FROM claims c, json_each(c.items_json) j
              WHERE c.employee_id=? AND c.id<>? AND c.status IN ('SUBMITTED','PENDING_APPROVAL')
              AND lower(json_extract(j.value,'$.vendor'))=lower(?)
              AND CAST(json_extract(j.value,'$.amount') AS REAL)=?
              AND json_extract(j.value,'$.date')=? LIMIT 1""",
              (claim["employee_id"],claim["id"],item["vendor"],amount,item["date"])).fetchone()
            if duplicate:
                blocked.append("R5"); reasons.append(f"Possible duplicate: {item['vendor']} ₹{amount:.2f} on {item['date']}.")
    if float(claim["total"])>25000:
        escalated.append("R6"); reasons.append("Claim total exceeds ₹25,000 and requires manager approval.")
    decision="DENIED" if blocked else ("ESCALATED" if escalated else "ALLOWED")
    return {"decision":decision,"rule_ids":list(dict.fromkeys(blocked+escalated)),
            "reasons":reasons or ["All core expense rules passed."],
            "risk_level":"HIGH" if blocked else ("MEDIUM" if escalated else "LOW"),"evidence":evidence}

def check_employee_scope(requester_id, resource_owner_id):
    if requester_id!=resource_owner_id:
        return {"decision":"DENIED","rule_ids":["R8"],"reasons":["Employees may access only their own profile and claims."],"risk_level":"HIGH","evidence":[]}
    return {"decision":"ALLOWED","rule_ids":[],"reasons":["Employee owns this resource."],"risk_level":"LOW","evidence":[]}

def check_manager_assignment(manager_id, claim):
    if manager_id!=claim["manager_id"]:
        return {"decision":"DENIED","rule_ids":["R9"],"reasons":["Claim is not assigned to this manager."],"risk_level":"HIGH","evidence":[]}
    return {"decision":"ALLOWED","rule_ids":[],"reasons":["Manager is assigned to this claim."],"risk_level":"LOW","evidence":[]}
