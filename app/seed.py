from app.db import get_db
from app.utils import dumps, now_iso

def seed_demo_data():
    with get_db() as db:
        if db.execute("SELECT COUNT(*) FROM employees").fetchone()[0]:
            return
        people = [
          ("emp-001","Aarav Sharma","aarav@example.test","employee","mgr-001","CC-BLR-01",100000.0,dumps({"currency":"INR"})),
          ("emp-002","Diya Patel","diya@example.test","employee","mgr-002","CC-PUN-02",75000.0,dumps({})),
          ("mgr-001","Rohan Mehta","rohan.manager@example.test","manager",None,"CC-BLR-01",0.0,dumps({})),
          ("mgr-002","Neha Verma","neha.manager@example.test","manager",None,"CC-PUN-02",0.0,dumps({}))
        ]
        db.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?)", people)
        db.execute("""INSERT INTO claims
          (id,employee_id,manager_id,title,purpose,cost_center,status,total,currency,items_json,policy_json,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          ("claim-seed-001","emp-001","mgr-001","Previous airport cab","Client visit","CC-BLR-01",
           "SUBMITTED",1200.0,"INR",
           dumps([{"vendor":"CityCab","date":"2026-10-20","amount":1200.0,"category":"transport","receipt_id":"seed"}]),
           dumps([]),now_iso(),now_iso()))
