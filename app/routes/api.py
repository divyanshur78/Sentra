from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from app.schemas import LoginRequest,ChatRequest,DraftClaimRequest,SubmitRequest,DecisionRequest,RedTeamRequest
from app.db import get_db
from app.utils import loads
from app.services.receipt_service import save_receipt
from app.services.agent_orchestrator import run_expense_agent
from app.services.claim_service import create_draft,get_claim,submit_claim,manager_decision,finalize_approved_claim
from app.services.memory_service import get_employee_memory
from app.services.policy_rules import RULES,check_employee_scope
from app.integrations.provider import get_governance

router=APIRouter(prefix="/api")

@router.post("/auth/login")
def login(body: LoginRequest):
    with get_db() as db: row=db.execute("SELECT id,name,email,role,manager_id,cost_center FROM employees WHERE id=?",(body.user_id,)).fetchone()
    if not row: raise HTTPException(404,"Demo user not found")
    return {"user":dict(row),"token":f"demo-token-{row['id']}","warning":"Demo-only authentication."}

@router.post("/chat")
def chat(body: ChatRequest):
    try: return run_expense_agent(body.employee_id,body.message)
    except ValueError as e: raise HTTPException(400,str(e))

@router.post("/receipts/upload")
async def upload_receipts(employee_id: str, files: List[UploadFile] = File(...)):
    output=[]
    for f in files:
        try: output.append(save_receipt(employee_id,f.filename or "receipt",await f.read()))
        except ValueError as e: raise HTTPException(400,str(e))
    return {"receipts":output}

@router.post("/claims/draft")
def draft(body: DraftClaimRequest):
    try: return create_draft(body.employee_id,body.title,body.purpose,[x.model_dump() for x in body.items],body.cost_center)
    except ValueError as e: raise HTTPException(400,str(e))

@router.get("/claims/{claim_id}")
def claim_detail(claim_id: str,requester_id: str):
    claim=get_claim(claim_id)
    if not claim: raise HTTPException(404,"Claim not found")
    if check_employee_scope(requester_id,claim["employee_id"])["decision"]=="DENIED": raise HTTPException(403,"R8: access denied")
    return claim

@router.post("/claims/{claim_id}/submit")
def submit(claim_id: str,body: SubmitRequest):
    try: return submit_claim(claim_id,body.employee_id,body.confirmation)
    except PermissionError as e: raise HTTPException(403,str(e))
    except ValueError as e: raise HTTPException(400,str(e))

@router.post("/claims/{claim_id}/approve")
def approve(claim_id: str,body: DecisionRequest):
    try: return {"claim":manager_decision(claim_id,body.manager_id,True,body.reason),"message":"Approved; manager must finalize submission."}
    except PermissionError as e: raise HTTPException(403,str(e))
    except ValueError as e: raise HTTPException(400,str(e))

@router.post("/claims/{claim_id}/reject")
def reject(claim_id: str,body: DecisionRequest):
    try: return manager_decision(claim_id,body.manager_id,False,body.reason)
    except PermissionError as e: raise HTTPException(403,str(e))
    except ValueError as e: raise HTTPException(400,str(e))

@router.post("/claims/{claim_id}/finalize")
def finalize(claim_id: str,body: DecisionRequest):
    try: return finalize_approved_claim(claim_id,body.manager_id)
    except PermissionError as e: raise HTTPException(403,str(e))
    except ValueError as e: raise HTTPException(400,str(e))

@router.get("/agent/trace/{run_id}")
def trace(run_id: str,requester_id: str):
    with get_db() as db: row=db.execute("SELECT * FROM agent_runs WHERE id=?",(run_id,)).fetchone()
    if not row: raise HTTPException(404,"Run not found")
    if row["employee_id"]!=requester_id: raise HTTPException(403,"R8: access denied")
    return {"run_id":run_id,"status":row["status"],"trace":loads(row["trace_json"],[])}

@router.get("/memory/{employee_id}")
def memory(employee_id: str,requester_id: str):
    if employee_id!=requester_id: raise HTTPException(403,"R8: access denied")
    result=get_employee_memory(employee_id)
    if not result: raise HTTPException(404,"Employee not found")
    return result

@router.get("/policy/rules")
def policy_rules():
    return {"rules":RULES,"note":"Person 1 provides R1-R9 evaluators; Person 3 owns gateway and R10."}

@router.get("/admin/metrics")
def admin_metrics(): return get_governance().metrics()

@router.get("/admin/policy-decisions")
def policy_decisions():
    with get_db() as db:
        rows=db.execute("SELECT * FROM audit_events WHERE event_type LIKE '%BLOCK%' OR event_type LIKE '%APPROVAL%' ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"decisions":[dict(x) for x in rows]}

@router.post("/redteam/run")
def redteam(body: RedTeamRequest): return get_governance().run_redteam(body.model_dump())
