from app.db import get_db
from app.utils import new_id, now_iso, dumps, loads
from app.services.policy_rules import evaluate_claim_rules, check_manager_assignment
from app.integrations.provider import get_governance
from app.schemas import ToolCall

def create_draft(employee_id,title,purpose,items,cost_center=None):
    with get_db() as db:
        employee=db.execute("SELECT * FROM employees WHERE id=?",(employee_id,)).fetchone()
        if not employee: raise ValueError("Employee not found")
        normalized=[]
        for item in items:
            item=dict(item)
            if item.get("receipt_id"):
                receipt=db.execute("SELECT * FROM receipts WHERE id=? AND employee_id=?",(item["receipt_id"],employee_id)).fetchone()
                if not receipt: raise ValueError("Receipt not found or not owned by employee")
                item["vendor"]=item.get("vendor") or receipt["vendor"]
                item["date"]=item.get("date") or receipt["expense_date"]
                item["amount"]=item.get("amount") or receipt["amount"]
                item["category"]=item.get("category") or receipt["category"]
            normalized.append(item)
        total=round(sum(float(x["amount"]) for x in normalized),2)
        cid=new_id("claim"); now=now_iso()
        db.execute("""INSERT INTO claims
          (id,employee_id,manager_id,title,purpose,cost_center,status,total,currency,items_json,policy_json,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (cid,employee_id,employee["manager_id"],title,purpose,cost_center or employee["cost_center"],
           "DRAFT",total,"INR",dumps(normalized),dumps([]),now,now))
        row=db.execute("SELECT * FROM claims WHERE id=?",(cid,)).fetchone()
        result=evaluate_claim_rules(db,row,normalized)
        db.execute("UPDATE claims SET policy_json=? WHERE id=?",(dumps(result),cid))
    get_governance().record_event("DRAFT_CREATED",f"Draft claim {cid} created",actor_id=employee_id,claim_id=cid,payload={"total":total})
    return get_claim(cid)

def get_claim(cid):
    with get_db() as db: row=db.execute("SELECT * FROM claims WHERE id=?",(cid,)).fetchone()
    if not row: return None
    item=dict(row); item["items"]=loads(item.pop("items_json"),[]); item["policy"]=loads(item.pop("policy_json"),[])
    return item

def submit_claim(cid,employee_id,confirmation=True):
    if not confirmation: raise ValueError("Explicit employee confirmation is required")
    with get_db() as db:
        row=db.execute("SELECT * FROM claims WHERE id=?",(cid,)).fetchone()
        if not row: raise ValueError("Claim not found")
        if row["employee_id"]!=employee_id: raise PermissionError("R8: claim belongs to another employee")
        if row["status"] not in ("DRAFT","NEEDS_CHANGES"): raise ValueError(f"Cannot submit claim in status {row['status']}")
        items=loads(row["items_json"],[]); rules=evaluate_claim_rules(db,row,items)
        db.execute("UPDATE claims SET policy_json=?,updated_at=? WHERE id=?",(dumps(rules),now_iso(),cid))
    if rules["decision"]=="DENIED":
        get_governance().record_event("SUBMISSION_BLOCKED","Core policy rules blocked submission",actor_id=employee_id,claim_id=cid,payload=rules)
        return {"claim":get_claim(cid),"policy":rules,"message":"Submission blocked"}
    gateway=get_governance().authorize_tool_call(ToolCall(actor_id=employee_id,tool_name="submit_claim",
       action="submit",resource_owner_id=employee_id,claim_id=cid,amount=row["total"]))
    if gateway.decision=="DENIED":
        return {"claim":get_claim(cid),"policy":gateway.model_dump(),"message":"Gateway denied submission"}
    if rules["decision"]=="ESCALATED" or gateway.decision=="ESCALATED":
        with get_db() as db:
            db.execute("UPDATE claims SET status='PENDING_APPROVAL',updated_at=? WHERE id=?",(now_iso(),cid))
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?)",(new_id("appr"),cid,row["manager_id"],"PENDING",None,now_iso(),None))
        get_governance().record_event("APPROVAL_REQUESTED","Claim routed to assigned manager",actor_id=employee_id,claim_id=cid,payload=rules)
        return {"claim":get_claim(cid),"policy":rules,"message":"Manager approval required"}
    with get_db() as db:
        db.execute("UPDATE claims SET status='SUBMITTED',submitted_at=?,updated_at=? WHERE id=?",(now_iso(),now_iso(),cid))
    get_governance().record_event("CLAIM_SUBMITTED","Claim submitted to mock ERP",actor_id=employee_id,claim_id=cid,payload=rules)
    return {"claim":get_claim(cid),"policy":rules,"message":"Claim submitted"}

def manager_decision(cid,manager_id,approve,reason=""):
    with get_db() as db:
        row=db.execute("SELECT * FROM claims WHERE id=?",(cid,)).fetchone()
        if not row: raise ValueError("Claim not found")
        access=check_manager_assignment(manager_id,row)
        if access["decision"]=="DENIED": raise PermissionError(access["reasons"][0])
        if row["status"]!="PENDING_APPROVAL": raise ValueError("Claim is not awaiting approval")
        items=loads(row["items_json"],[]); rules=evaluate_claim_rules(db,row,items)
        if approve and (rules["decision"]=="DENIED" or not any(x.get("receipt_id") for x in items)):
            raise ValueError("R7: claim with missing receipt or blocked rule cannot be approved")
        status="APPROVED" if approve else "REJECTED"
        db.execute("UPDATE claims SET status=?,decision_reason=?,updated_at=? WHERE id=?",(status,reason,now_iso(),cid))
        db.execute("UPDATE approvals SET status=?,reason=?,decided_at=? WHERE claim_id=? AND status='PENDING'",(status,reason,now_iso(),cid))
    get_governance().record_event("MANAGER_APPROVED" if approve else "MANAGER_REJECTED",f"Manager {status.lower()} claim",actor_id=manager_id,claim_id=cid,payload={"reason":reason})
    return get_claim(cid)

def finalize_approved_claim(cid,manager_id):
    with get_db() as db:
        row=db.execute("SELECT * FROM claims WHERE id=?",(cid,)).fetchone()
        if not row: raise ValueError("Claim not found")
        if row["status"]!="APPROVED": raise ValueError("Claim must be manager-approved first")
        if row["manager_id"]!=manager_id: raise PermissionError("R9: unauthorized manager")
        rules=evaluate_claim_rules(db,row,loads(row["items_json"],[]))
        if rules["decision"]=="DENIED": raise ValueError("Final policy check failed")
        db.execute("UPDATE claims SET status='SUBMITTED',submitted_at=?,updated_at=? WHERE id=?",(now_iso(),now_iso(),cid))
    get_governance().record_event("CLAIM_SUBMITTED","Approved claim submitted to mock ERP",actor_id=manager_id,claim_id=cid,payload=rules)
    return get_claim(cid)
