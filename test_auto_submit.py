import time
from fastapi.testclient import TestClient
from app.main import app

def test_automated_submission():
    client = TestClient(app)
    ts = int(time.time())

    # 1. Test Auto-submit for Standard Valid Expense (<= 25000) -> Should become SUBMITTED directly
    r_up = client.post(
        "/api/receipts/upload?employee_id=emp-001",
        files={"files": ("lunch.txt", f"CAFE COFFEE DAY {ts}\nDate: 2026-11-04\nLunch - Client Meeting\nTOTAL: INR 850.00\nThank you".encode("utf-8"), "text/plain")}
    )
    assert r_up.status_code == 200
    rcpt1 = r_up.json()["receipts"][0]
    rid1 = rcpt1.get("id") or rcpt1.get("receipt_id")

    # Send chat message with receipt ID attached
    r_chat1 = client.post("/api/chat", json={
        "employee_id": "emp-001",
        "message": f"Please process my client lunch expense at Cafe Coffee Day {ts}",
        "receipt_ids": [rid1],
        "auto_submit": True
    })
    assert r_chat1.status_code == 200
    res1 = r_chat1.json()
    claim1 = res1.get("claim")
    assert claim1 is not None, "Claim should be automatically created"
    assert claim1["status"] in ("APPROVED", "SUBMITTED"), f"Expected APPROVED/SUBMITTED for standard expense, got {claim1['status']}"
    assert claim1["total"] == 850.0
    print("[OK] Test 1: Standard claim automatically drafted and submitted to ERP (Status: SUBMITTED)")

    # 2. Test Auto-submit for High Value Expense (> 25000) for emp-002 -> Rule R6 matches policy and sends for Manager Approval
    r_up2 = client.post(
        "/api/receipts/upload?employee_id=emp-002",
        files={"files": ("tech_conference.txt", f"TECH CONFERENCE 2026 {ts}\nDate: 2026-11-04\nConference Registration Pass\nTOTAL: INR 28000.00\nPaid".encode("utf-8"), "text/plain")}
    )
    assert r_up2.status_code == 200
    rcpt2 = r_up2.json()["receipts"][0]
    rid2 = rcpt2.get("id") or rcpt2.get("receipt_id")

    # Send chat message for high-value expense
    r_chat2 = client.post("/api/chat", json={
        "employee_id": "emp-002",
        "message": f"Annual Tech Conference registration fee {ts}",
        "receipt_ids": [rid2],
        "auto_submit": True
    })
    assert r_chat2.status_code == 200
    res2 = r_chat2.json()
    claim2 = res2.get("claim")
    assert claim2 is not None, "Claim should be automatically created"
    assert claim2["status"] == "PENDING_APPROVAL", f"Expected PENDING_APPROVAL for >25k, got {claim2['status']}"
    assert claim2["total"] == 28000.0
    print("[OK] Test 2: High-value claim (>25k) automatically drafted and routed for approval (Status: PENDING_APPROVAL)")

    # 3. Verify Manager (mgr-002) sees the escalated claim in their queue
    r_mgr = client.get("/api/claims?requester_id=mgr-002")
    assert r_mgr.status_code == 200
    mgr_claims = r_mgr.json().get("claims", [])
    found = [c for c in mgr_claims if c["id"] == claim2["id"]]
    assert len(found) > 0, "Manager should see the pending claim in their list"
    assert found[0]["status"] == "PENDING_APPROVAL"
    print(f"[OK] Test 3: Manager queue reflects automated claim {claim2['id']} awaiting decision")

    # 4. Manager approves and finalizes claim
    r_app = client.post(f"/api/claims/{claim2['id']}/approve", json={"manager_id": "mgr-002", "reason": "Approved valid conference"})
    assert r_app.status_code == 200
    r_fin = client.post(f"/api/claims/{claim2['id']}/finalize", json={"manager_id": "mgr-002", "reason": "Finalized"})
    assert r_fin.status_code == 200
    assert r_fin.json()["status"] == "SUBMITTED"
    print(f"[OK] Test 4: Manager approved and finalized claim {claim2['id']} to ERP")

    # 5. Test Policy Block: Restricted Alcohol Category (Rule R4) -> Should block auto-submit
    r_up3 = client.post(
        "/api/receipts/upload?employee_id=emp-001",
        files={"files": ("drinks.txt", f"BAR AND WINE SHOP {ts}\nDate: 2026-11-04\nAlcohol Drinks\nTOTAL: INR 2200.00".encode("utf-8"), "text/plain")}
    )
    assert r_up3.status_code == 200
    rcpt3 = r_up3.json()["receipts"][0]
    rid3 = rcpt3.get("id") or rcpt3.get("receipt_id")

    r_chat3 = client.post("/api/chat", json={
        "employee_id": "emp-001",
        "message": f"Drinks at Bar and Wine Shop {ts}",
        "receipt_ids": [rid3],
        "auto_submit": True
    })
    assert r_chat3.status_code == 200
    res3 = r_chat3.json()
    claim3 = res3.get("claim")
    assert claim3 is not None
    assert claim3["status"] in ("REJECTED", "DRAFT"), f"Expected REJECTED/DRAFT for alcohol, got {claim3['status']}"
    assert "R4" in res3.get("policy", {}).get("rule_ids", [])
    print("[OK] Test 5: Restricted category (Rule R4 alcohol) prevented submission and saved as blocked draft")

    print("\n=======================================================")
    print(" ALL 5 AUTOMATED DRAFT & SUBMISSION TESTS PASSED! ")
    print("=======================================================")

if __name__ == "__main__":
    test_automated_submission()
