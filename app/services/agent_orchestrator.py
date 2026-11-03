from app.services.llm_service import interpret_expense_request
from app.services.memory_service import get_employee_memory
from app.utils import new_id, now_iso, dumps
from app.db import get_db
from app.integrations.provider import get_governance

def run_expense_agent(employee_id,message):
    run_id=new_id("run"); trace=[]
    memory=get_employee_memory(employee_id)
    if not memory: raise ValueError("Employee not found")
    intent=interpret_expense_request(message)
    for event,detail,payload in [
      ("MEMORY_LOOKUP","Loaded employee profile and recent claims",{"recent_claim_count":len(memory["recent_claims"])}),
      ("INTENT_PARSED","Parsed employee expense request",intent)]:
        trace.append({"step":event,"detail":detail,"data":payload,"timestamp":now_iso()})
        get_governance().record_event(event,detail,actor_id=employee_id,run_id=run_id,payload=payload)
    with get_db() as db:
        db.execute("INSERT INTO agent_runs VALUES (?,?,?,?,?,?)",(run_id,employee_id,None,"WAITING_FOR_RECEIPTS",dumps(trace),now_iso()))
    return {"run_id":run_id,"employee_id":employee_id,"intent":intent,"memory":memory,
            "next_action":"UPLOAD_RECEIPTS_AND_CREATE_DRAFT",
            "message":"Request understood. Upload receipts, review extracted details, then create your draft claim."}
