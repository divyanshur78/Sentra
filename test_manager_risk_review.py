import time
import sqlite3
from fastapi.testclient import TestClient
from app.main import app

def test_risk_model_and_manager_review():
    client = TestClient(app)
    ts = int(time.time())

    # Clean database test records for determinism
    with sqlite3.connect("./sentra.db") as conn:
        conn.execute("DELETE FROM claims WHERE id LIKE 'claim-%'")
        conn.execute("DELETE FROM receipts WHERE id LIKE 'rcpt-%'")
        conn.commit()

    # 1. Create and submit LOW-RISK claim (amount = 1200 <= 25k, compliant)
    r_up1 = client.post(
        "/api/receipts/upload?employee_id=emp-001",
        files={"files": ("low_risk.txt", f"BLUE TOKAI CAFE {ts}\nDate: 2026-11-04\nCoffee & Lunch\nTOTAL: INR 1200.00\nPaid".encode("utf-8"), "text/plain")}
    )
    assert r_up1.status_code == 200
    rid1 = r_up1.json()["receipts"][0]["id"]

    r_chat1 = client.post("/api/chat", json={
        "employee_id": "emp-001",
        "message": f"Client coffee at Blue Tokai {ts}",
        "receipt_ids": [rid1],
        "auto_submit": True
    })
    assert r_chat1.status_code == 200
    c1 = r_chat1.json()["claim"]
    assert c1["status"] == "APPROVED", f"Low risk claim should be AUTO-APPROVED (status=APPROVED), got {c1['status']}"
    assert "auto-approved" in (c1.get("decision_reason") or "").lower()
    print(f"[OK] Low-Risk Model: Claim {c1['id']} (Rs.{c1['total']:,.0f}) AUTO-APPROVED by low-risk engine")

    # 2. Create and submit MODERATE-RISK claim (amount = 28,000 > 25k threshold, Rule R6) for emp-002
    r_up2 = client.post(
        "/api/receipts/upload?employee_id=emp-002",
        files={"files": ("moderate_risk.txt", f"TECH FORUM 2026 {ts}\nDate: 2026-11-04\nConference Fee\nTOTAL: INR 28000.00\nPaid".encode("utf-8"), "text/plain")}
    )
    assert r_up2.status_code == 200
    rid2 = r_up2.json()["receipts"][0]["id"]

    r_chat2 = client.post("/api/chat", json={
        "employee_id": "emp-002",
        "message": f"Tech Forum Conference Pass {ts}",
        "receipt_ids": [rid2],
        "auto_submit": True
    })
    assert r_chat2.status_code == 200
    c2 = r_chat2.json()["claim"]
    assert c2["status"] == "PENDING_APPROVAL", f"Moderate risk claim should require review (PENDING_APPROVAL), got {c2['status']}"
    print(f"[OK] Moderate-Risk Model: Claim {c2['id']} (Rs.{c2['total']:,.0f}) routed for MANAGER REVIEW (Rule R6)")

    # 3. Create and submit HIGH-RISK claim (Rule R4: alcohol) -> Should be DECLINED
    r_up3 = client.post(
        "/api/receipts/upload?employee_id=emp-001",
        files={"files": ("high_risk.txt", f"WINE & SPIRITS {ts}\nDate: 2026-11-04\nAlcohol Drinks\nTOTAL: INR 3500.00\nPaid".encode("utf-8"), "text/plain")}
    )
    assert r_up3.status_code == 200
    rid3 = r_up3.json()["receipts"][0]["id"]

    r_chat3 = client.post("/api/chat", json={
        "employee_id": "emp-001",
        "message": f"Drinks at Wine & Spirits {ts}",
        "receipt_ids": [rid3],
        "auto_submit": True
    })
    assert r_chat3.status_code == 200
    c3 = r_chat3.json()["claim"]
    assert c3["status"] == "REJECTED", f"High risk claim should be DECLINED (status=REJECTED), got {c3['status']}"
    assert "declined" in (c3.get("decision_reason") or "").lower()
    print(f"[OK] High-Risk Model: Claim {c3['id']} (Rs.{c3['total']:,.0f}) DECLINED by policy guardrail (Rule R4)")

    # 4. Verify visibility for both Employee and Manager
    # Employee view:
    r_emp = client.get("/api/claims?requester_id=emp-001")
    assert r_emp.status_code == 200
    emp_claims = {c["id"]: c["status"] for c in r_emp.json()["claims"]}
    assert emp_claims[c1["id"]] == "APPROVED", "Employee should see Low risk as APPROVED"
    assert emp_claims[c3["id"]] == "REJECTED", "Employee should see High risk as REJECTED (Declined)"
    print("[OK] Visibility: Employee emp-001 accurately sees Auto-approved & Declined claim statuses")

    # Manager view for mgr-001:
    r_mgr1 = client.get("/api/claims?requester_id=mgr-001")
    assert r_mgr1.status_code == 200
    mgr1_claims = {c["id"]: c["status"] for c in r_mgr1.json()["claims"]}
    assert mgr1_claims[c1["id"]] == "APPROVED", "Manager should see Low risk as APPROVED"
    assert mgr1_claims[c3["id"]] == "REJECTED", "Manager should see High risk as REJECTED"
    print("[OK] Visibility: Manager mgr-001 accurately sees Auto-approved & Declined claims in portfolio")

    # Manager view for mgr-002 (assigned to emp-002's moderate claim):
    r_mgr2 = client.get("/api/claims?requester_id=mgr-002")
    assert r_mgr2.status_code == 200
    mgr2_claims = {c["id"]: c["status"] for c in r_mgr2.json()["claims"]}
    assert mgr2_claims[c2["id"]] == "PENDING_APPROVAL", "Manager mgr-002 must see Moderate claim in Approval Queue"
    print("[OK] Visibility: Manager mgr-002 accurately sees Moderate claim awaiting review")

    # 5. Test Manager AI Chatbot Review Feature
    # Manager mgr-001 asks for general review
    r_review = client.post("/api/chat", json={
        "employee_id": "mgr-001",
        "message": "Give me a review of claims"
    })
    assert r_review.status_code == 200
    review_msg = r_review.json()["message"]
    assert "LOW RISK" in review_msg
    assert "HIGH RISK" in review_msg
    assert "Summary" in review_msg
    print("\n[OK] Manager AI Chatbot Review:")
    for line in review_msg.splitlines()[:12]:
        print("     " + line.encode("ascii", "ignore").decode())

    # Manager mgr-001 asks to review specific high-risk claim
    r_specific = client.post("/api/chat", json={
        "employee_id": "mgr-001",
        "message": f"Review claim {c3['id']}"
    })
    assert r_specific.status_code == 200
    spec_msg = r_specific.json()["message"]
    assert c3["id"] in spec_msg
    assert "HIGH RISK" in spec_msg
    assert "Declined" in spec_msg
    print(f"\n[OK] Manager AI Chatbot Specific Claim Review for {c3['id']}:")
    for line in spec_msg.splitlines()[:8]:
        print("     " + line.encode("ascii", "ignore").decode())

    print("\n==================================================================")
    print(" ALL RISK TIERS & MANAGER AI CHATBOT REVIEWS VERIFIED CLEANLY! ")
    print("==================================================================")

if __name__ == "__main__":
    test_risk_model_and_manager_review()

