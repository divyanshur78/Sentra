"""Script to patch App.jsx for backend integration."""
import re

path = 'Sentrafrnt/src/App.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the ClaimDetail function (it's a one-liner from line 1253)
new_claim_detail = '''function ClaimDetail({claim, onClose, role, userId, onDecisionRequest}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="detail-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">CLAIM DETAILS · {claim.id}</span>
            <h2>{claim.purpose}</h2>
          </div>
          <button onClick={onClose}>×</button>
        </div>
        <div className="detail-amount">{money(claim.amount)} <Status status={claim.status}/></div>
        <div className="detail-grid">
          <div><small>EMPLOYEE</small><b>{claim.person}</b></div>
          <div><small>SUBMITTED</small><b>{claim.date}</b></div>
          <div><small>CATEGORY</small><b>{claim.category}</b></div>
          <div><small>RISK LEVEL</small><b>{claim.risk}</b></div>
        </div>
        <div className="explain-card">
          <span>◈ POLICY EXPLANATION</span>
          <b>{claim.amount > 25000 ? 'Rule R6 · Manager approval required' : 'Policy checks passed'}</b>
          <p>{claim.amount > 25000
            ? 'Claim total exceeds the ₹25,000 auto-approval threshold. Receipts must be valid and a manager must approve before submission.'
            : 'No high-risk policy condition is currently flagged for this claim.'}
          </p>
        </div>
        {claim.decisionReason && (
          <div className="decision-history-card">
            <span>MANAGER DECISION · {claim.status.toUpperCase()}</span>
            <b>Recorded by {claim.decisionBy || 'Manager'}</b>
            <p>{claim.decisionReason}</p>
          </div>
        )}
        {claim.policyReason && (
          <div className="decision-history-card">
            <span>POLICY RESULT</span>
            <p>{claim.policyReason}</p>
          </div>
        )}
        <div className="receipt-placeholder">
          <span>▧</span>
          <div>
            <b>{claim.items} receipt item(s)</b>
            <small>Receipt details available in the backend audit trail.</small>
          </div>
          <span className="verified-label">BACKEND DATA</span>
        </div>
        {role === 'Manager' && claim.status === 'Needs approval' && onDecisionRequest && (
          <div className="decision-modal-actions" style={{ marginTop: 16 }}>
            <button className="approve-button" onClick={() => { onClose(); onDecisionRequest(claim.id, 'Approved'); }}>
              ✓ Approve
            </button>
            <button className="reject-button" onClick={() => { onClose(); onDecisionRequest(claim.id, 'Rejected'); }}>
              × Reject
            </button>
          </div>
        )}
        <button className="primary-button modal-close" onClick={onClose}>Close details</button>
      </div>
    </div>
  );
}'''

# Find and replace the ClaimDetail function (one-liner starting with "function ClaimDetail")
pattern = r'function ClaimDetail\(\{claim,onClose\}\) \{ return.*?; \}'
new_content = re.sub(pattern, new_claim_detail, content, flags=re.DOTALL)

if new_content == content:
    print("WARNING: ClaimDetail not replaced, trying alternate pattern...")
    # Try just replacing by line number
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('function ClaimDetail('):
            lines[i] = new_claim_detail
            break
    new_content = '\n'.join(lines)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done patching App.jsx")
print(f"File size: {len(new_content)} chars")

