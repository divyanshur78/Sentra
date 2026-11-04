import re

path = 'Sentrafrnt/src/App.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update createClaim mapping
old_create_map = """    const statusMap = {
      PENDING_APPROVAL: 'Needs approval',
      SUBMITTED: 'Submitted',
      APPROVED: 'Approved',
      REJECTED: 'Rejected',
      DRAFT: result.policy?.decision === 'DENIED' ? 'Blocked' : 'Draft'
    };

    // 4. Map backend response to existing UI
    const newClaim = {
      id: backendClaim.id,
      person: userName,
      purpose: backendClaim.title || formData.purpose,
      vendor: firstItem.vendor || formData.vendor,
      amount: Number(backendClaim.total || formData.amount),
      date: firstItem.date || formData.date,
      category: firstItem.category || formData.category,
      status: statusMap[backendClaim.status] || backendClaim.status,
      risk: Number(backendClaim.total || 0) > 25000 ? 'High' : 'Low',
      items: backendClaim.items?.length || 1,
      initials: userName.split(' ')
        .map(word => word[0])
        .join('')
        .slice(0, 2)
        .toUpperCase(),
      receiptName: formData.receipt.name,
      policyReason: result.message || 'Backend policy evaluation completed.'
    };"""

new_create_map = """    const isAutoApproved = backendClaim.status === 'APPROVED' && (result.risk_level === 'LOW' || (backendClaim.decision_reason || '').toLowerCase().includes('auto-approved'));
    const isDeclined = backendClaim.status === 'REJECTED' || result.risk_level === 'HIGH' || (backendClaim.decision_reason || '').toLowerCase().includes('declined');
    const statusLabel = isAutoApproved ? 'Auto-approved'
                      : isDeclined ? 'Declined'
                      : backendClaim.status === 'PENDING_APPROVAL' ? 'Needs review'
                      : backendClaim.status === 'APPROVED' ? 'Approved'
                      : backendClaim.status === 'SUBMITTED' ? 'Submitted'
                      : 'Draft';
    const riskTier = result.risk_level === 'HIGH' || isDeclined ? 'High'
                   : result.risk_level === 'MEDIUM' || Number(backendClaim.total || 0) > 25000 ? 'Moderate'
                   : 'Low';

    // 4. Map backend response to existing UI
    const newClaim = {
      id: backendClaim.id,
      person: userName,
      purpose: backendClaim.title || formData.purpose,
      vendor: firstItem.vendor || formData.vendor,
      amount: Number(backendClaim.total || formData.amount),
      date: firstItem.date || formData.date,
      category: firstItem.category || formData.category,
      status: statusLabel,
      risk: riskTier,
      items: backendClaim.items?.length || 1,
      initials: userName.split(' ')
        .map(word => word[0])
        .join('')
        .slice(0, 2)
        .toUpperCase(),
      receiptName: formData.receipt.name,
      decisionReason: backendClaim.decision_reason || result.message || '',
      policyReason: result.message || backendClaim.decision_reason || 'Backend policy evaluation completed.'
    };"""

if old_create_map in content:
    content = content.replace(old_create_map, new_create_map)
    print("Updated createClaim mapping")
else:
    print("Could not match old_create_map")

# 2. Update ClaimDetail explanation
old_detail_explain = """        <div className="explain-card">
          <span>◈ POLICY EXPLANATION</span>
          <b>{claim.amount > 25000 ? 'Rule R6 · Manager approval required' : 'Policy checks passed'}</b>
          <p>{claim.amount > 25000
            ? 'Claim total exceeds the ₹25,000 auto-approval threshold. Receipts must be valid and a manager must approve before submission.'
            : 'No high-risk policy condition is currently flagged for this claim.'}
          </p>
        </div>"""

new_detail_explain = """        <div className="explain-card">
          <span>◈ RISK ASSESSMENT & POLICY GOVERNANCE</span>
          <b>
            {claim.risk === 'Low'
              ? '🟢 Low Risk · Auto-Approved'
              : claim.risk === 'Moderate'
                ? '🟡 Moderate Risk · Manager Review Required'
                : '🔴 High Risk · Declined by Guardrails'}
          </b>
          <p>
            {claim.risk === 'Low'
              ? 'Verified compliant with valid receipts and normal business categories (Rules R1–R5, R7–R9). Automatically approved by the low-risk engine and submitted to ERP.'
              : claim.risk === 'Moderate'
                ? 'Claim total exceeds the ₹25,000 threshold (Rule R6). Escalated to assigned manager for review and explicit decision.'
                : (claim.decisionReason || 'Declined due to policy violation (missing receipts, non-reimbursable category, or duplicate expense).')}
          </p>
        </div>"""

if old_detail_explain in content:
    content = content.replace(old_detail_explain, new_detail_explain)
    print("Updated ClaimDetail explanation")
else:
    pattern = r'<div className="explain-card">.*?<span>.*?POLICY EXPLANATION.*?</div>'
    content = re.sub(pattern, new_detail_explain, content, flags=re.DOTALL)
    print("Regex updated ClaimDetail explanation")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved updated App.jsx")

