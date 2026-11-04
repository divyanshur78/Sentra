with open('app/services/agent_orchestrator.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Normalize line endings to \n
c = c.replace('\r\n', '\n')

old = """    # If receipts present, automate draft creation & policy-governed submission!
    if target_receipts:
        items = []
        for r in target_receipts:
            items.append({
                "receipt_id": r["id"],
                "vendor": r.get("vendor") or intent.get("vendor") or "Vendor",
                "date": r.get("expense_date") or now_iso()[:10],
                "amount": float(r.get("amount") or intent.get("amount") or 100.0),
                "category": r.get("category") or intent.get("category") or "other",
                "description": intent.get("purpose") or "Automated expense claim"
            })"""

new = """    # If receipts present, automate draft creation & policy-governed submission!
    if target_receipts:
        items = []
        for r in target_receipts:
            rcpt_amount = r.get("amount")
            final_amount = rcpt_amount if rcpt_amount is not None else intent.get("amount")

            if final_amount is None:
                vendor_txt = r.get("vendor") or "your uploaded bill"
                response_text = (
                    f"I scanned {vendor_txt}, but could not clearly read the total bill amount from the document. "
                    "Please state the total amount (e.g. 'The total bill is Rs. 1450') so I can process and evaluate your claim."
                )
                return {
                    "run_id": run_id,
                    "employee_id": employee_id,
                    "intent": intent,
                    "memory": memory,
                    "claim": None,
                    "policy": None,
                    "next_action": "NEED_AMOUNT_CONFIRMATION",
                    "message": response_text,
                    "response": response_text
                }

            items.append({
                "receipt_id": r["id"],
                "vendor": r.get("vendor") or intent.get("vendor") or "Vendor",
                "date": r.get("expense_date") or now_iso()[:10],
                "amount": float(final_amount),
                "category": r.get("category") or intent.get("category") or "other",
                "description": intent.get("purpose") or "Automated expense claim"
            })"""

if old in c:
    c = c.replace(old, new)
    with open('app/services/agent_orchestrator.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print("SUCCESS: 100 fallback removed from agent_orchestrator.py")
else:
    print("ERROR: Old pattern not found in agent_orchestrator.py")

