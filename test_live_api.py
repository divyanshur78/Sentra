import sys
import requests

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

print("1. Checking Server Health...")
r = requests.get(f"{BASE_URL}/health")
assert r.status_code == 200
print("   Health Check OK:", r.json())

print("\n2. Uploading Photo Receipt (test_receipt_clear.png)...")
with open("test_receipt_clear.png", "rb") as f:
    files = {"files": ("starbucks_receipt.png", f, "image/png")}
    r_img = requests.post(f"{BASE_URL}/api/receipts/upload?employee_id=emp-001", files=files)
assert r_img.status_code == 200, f"Upload failed: {r_img.text}"
rcpt = r_img.json()["receipts"][0]
print(f"   Photo Extracted Vendor: {rcpt['vendor']}")
print(f"   Photo Extracted Amount: Rs. {rcpt['amount']}")
print(f"   Photo Extracted Category: {rcpt['category']}")
assert rcpt['amount'] == 600.0, f"Expected 600.0, got {rcpt['amount']}"
assert rcpt['vendor'] == "STARBUCKS COFFEE", f"Expected STARBUCKS COFFEE, got {rcpt['vendor']}"

print("\n3. Testing Automated Draft & Policy Submission via AI Agent...")
r_chat = requests.post(f"{BASE_URL}/api/chat", json={
    "employee_id": "emp-001",
    "message": "Submit my Starbucks expense claim",
    "receipt_ids": [rcpt["id"]],
    "auto_submit": True
})
assert r_chat.status_code == 200
chat_res = r_chat.json()
claim = chat_res.get("claim")
print(f"   Claim Created: {claim['id']}")
print(f"   Claim Title: {claim['title']}")
print(f"   Claim Total: Rs. {claim['total']}")
print(f"   Claim Status: {claim['status']}")
print(f"   Decision: {claim.get('decision_reason')}")
assert claim["total"] == 600.0, "Claim total must be 600.0, NOT 100!"
assert claim["status"] == "APPROVED", "Low risk claim must be AUTO-APPROVED (status=APPROVED)"

print("\n4. Testing PDF Bill Upload & Extraction...")
import fitz
doc = fitz.open()
p = doc.new_page()
p.insert_text((50, 50), "INDIGO AIRLINES\nBoarding Pass\nDate: 2026-11-04\nTotal Amount: INR 4850.00\nPayment: Confirmed")
pdf_bytes = doc.tobytes()
files_pdf = {"files": ("indigo_ticket.pdf", pdf_bytes, "application/pdf")}
r_pdf = requests.post(f"{BASE_URL}/api/receipts/upload?employee_id=emp-001", files=files_pdf)
assert r_pdf.status_code == 200
rcpt_pdf = r_pdf.json()["receipts"][0]
print(f"   PDF Extracted Vendor: {rcpt_pdf['vendor']}")
print(f"   PDF Extracted Amount: Rs. {rcpt_pdf['amount']}")
print(f"   PDF Extracted Category: {rcpt_pdf['category']}")
assert rcpt_pdf['amount'] == 4850.0, f"Expected 4850.0, got {rcpt_pdf['amount']}"

print("\n5. Testing Manager AI Chatbot Risk Review...")
r_mgr = requests.post(f"{BASE_URL}/api/chat", json={
    "employee_id": "mgr-001",
    "message": "Review my team's claims and give me a risk assessment"
})
assert r_mgr.status_code == 200
mgr_res = r_mgr.json()
print("   Manager AI Review Response:")
print("\n".join("     " + line for line in mgr_res.get("message", "").splitlines()[:12]))

print("\n=======================================================")
print(" ALL LIVE END-TO-END VERIFICATIONS PASSED SUCCESSFULLY! ")
print("=======================================================")
