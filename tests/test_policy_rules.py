from app.services.policy_rules import check_employee_scope, check_manager_assignment
from app.db import init_db, get_db
from app.seed import seed_demo_data

def test_employee_scope():
    assert check_employee_scope("emp-001","emp-001")["decision"]=="ALLOWED"
    assert check_employee_scope("emp-001","emp-002")["rule_ids"]==["R8"]

def test_manager_assignment():
    init_db(); seed_demo_data()
    with get_db() as db:
        claim=db.execute("SELECT * FROM claims WHERE id='claim-seed-001'").fetchone()
        assert check_manager_assignment("mgr-001",claim)["decision"]=="ALLOWED"
        assert check_manager_assignment("mgr-002",claim)["decision"]=="DENIED"
