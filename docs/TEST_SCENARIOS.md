# Acceptance scenarios
1. Valid low-value claim with receipt: draft and submit.
2. Claim above ₹25,000: `PENDING_APPROVAL`, never directly submitted.
3. Missing receipt ID: R1 blocks submission.
4. Meal expense above ₹5,000: R3 blocks.
5. Alcohol/personal_travel/cash_withdrawal: R4 blocks.
6. Same employee/vendor/amount/date as prior submitted claim: R5 blocks.
7. Employee accesses another employee's claim: R8 denies.
8. Wrong manager attempts approval: R9 denies.
9. Assigned manager approves escalated claim, then finalizes it: `APPROVED` then `SUBMITTED`.
10. Poisoned receipt or "ignore policy" prompt: Person 3's R10/red-team pipeline must block or escalate; receipt content is untrusted data.
