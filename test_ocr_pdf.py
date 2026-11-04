import sys, io
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw, ImageFont
import fitz
from app.db import get_db

# Clean database for clean test run
with get_db() as db:
    db.execute('DELETE FROM claims')
    db.execute('DELETE FROM receipts')

from app.services.receipt_service import save_receipt
from app.services.agent_orchestrator import run_expense_agent

print('--- TEST 1: PDF BILL EXTRACTION ---')
doc = fitz.open()
p = doc.new_page()
p.insert_text((50, 50), 'AIR INDIA EXPRESS\nFlight IX-1234 Bangalore to Delhi\nDate: 2026-11-04\nPassenger: Aarav Sharma\nTotal Amount: INR 28,500.00\nPayment: Paid')
pdf_bytes = doc.tobytes()

r_pdf = save_receipt('emp-001', 'flight_ticket.pdf', pdf_bytes)
print('PDF Extracted Vendor:', r_pdf['vendor'])
print('PDF Extracted Amount:', r_pdf['amount'])
print('PDF Extracted Category:', r_pdf['category'])
assert r_pdf['amount'] == 28500.0, f"Expected 28500.0, got {r_pdf['amount']}"

agent_res_pdf = run_expense_agent('emp-001', 'Please submit my flight expense', [r_pdf['id']], auto_submit=True)
claim_pdf = agent_res_pdf.get('claim')
print('PDF Claim Amount:', claim_pdf['total'])
print('PDF Claim Status:', claim_pdf['status'])
assert claim_pdf['total'] == 28500.0, 'Amount must be 28500.0, NOT 100!'
assert claim_pdf['status'] == 'PENDING_APPROVAL', 'Should be PENDING_APPROVAL (Moderate Risk), NOT Auto-Approved!'
print('[PASS] PDF Bill read correctly: Rs. 28,500 -> Routed for Manager Review (Moderate Risk)')

print('\n--- TEST 2: PHOTO / IMAGE BILL EXTRACTION (with Windows OCR) ---')
try:
    font = ImageFont.truetype('arial.ttf', 24)
except:
    font = ImageFont.load_default()

img = Image.new('RGB', (800, 400), color='white')
d = ImageDraw.Draw(img)
d.text((40, 40), 'BLUE TOKAI COFFEE ROASTERS', fill='black', font=font)
d.text((40, 90), 'Date: 2026-11-04', fill='black', font=font)
d.text((40, 140), 'Cappuccino x2: 480.00', fill='black', font=font)
d.text((40, 190), 'Croissant: 240.00', fill='black', font=font)
d.text((40, 240), 'TOTAL AMOUNT: INR 720.00', fill='black', font=font)
d.text((40, 290), 'Paid by Card', fill='black', font=font)

img_buf = io.BytesIO()
img.save(img_buf, format='PNG')
img_bytes = img_buf.getvalue()

r_img = save_receipt('emp-001', 'cafe_receipt.png', img_bytes)
print('Photo Extracted Vendor:', r_img['vendor'])
print('Photo Extracted Amount:', r_img['amount'])
print('Photo Extracted Category:', r_img['category'])
assert r_img['amount'] == 720.0, f"Expected 720.0, got {r_img['amount']}"

agent_res_img = run_expense_agent('emp-001', 'Submit my cafe bill', [r_img['id']], auto_submit=True)
claim_img = agent_res_img.get('claim')
print('Photo Claim Amount:', claim_img['total'])
print('Photo Claim Status:', claim_img['status'])
assert claim_img['total'] == 720.0, 'Amount must be 720.0, NOT 100!'
assert claim_img['status'] == 'APPROVED', 'Should be APPROVED (Low Risk Auto-approved)'
print('[PASS] Photo Bill read correctly: Rs. 720 -> Low Risk Auto-Approved by Model!')

print('\n--- TEST 3: BLANK / UNREADABLE IMAGE PREVENTS FAKE 100 AUTO-APPROVAL ---')
blank_img = Image.new('RGB', (200, 100), color='white')
b_buf = io.BytesIO()
blank_img.save(b_buf, format='PNG')
r_blank = save_receipt('emp-001', 'blurry_photo.png', b_buf.getvalue())
agent_blank = run_expense_agent('emp-001', 'Submit my bill', [r_blank['id']], auto_submit=True)
print('Agent response when amount unreadable:')
print(' ', agent_blank['message'])
assert agent_blank['claim'] is None, 'Should NOT create or auto-approve a claim with fake 100!'
assert 'could not clearly read the total bill amount' in agent_blank['message']
print('[PASS] Unreadable image properly stopped and asked employee for amount!')

print('\n======================================================')
print(' ALL 3 TESTS PASSED: PDF & PHOTO OCR BILL READING VERIFIED! ')
print('======================================================')
