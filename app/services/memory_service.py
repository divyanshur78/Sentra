from app.db import get_db
from app.utils import loads

def get_employee_memory(employee_id):
    with get_db() as db:
        employee=db.execute("SELECT * FROM employees WHERE id=?",(employee_id,)).fetchone()
        if not employee: return None
        claims=db.execute("SELECT id,title,total,status,created_at FROM claims WHERE employee_id=? ORDER BY created_at DESC LIMIT 5",(employee_id,)).fetchall()
    return {"employee_id":employee["id"],"name":employee["name"],"cost_center":employee["cost_center"],
            "manager_id":employee["manager_id"],"monthly_limit":employee["monthly_limit"],
            "preferences":loads(employee["preferences"],{}),"recent_claims":[dict(x) for x in claims]}
