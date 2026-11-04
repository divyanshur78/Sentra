import re

path = 'Sentrafrnt/src/App.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update manager prompts in AssistantPanel
old_manager_prompts = """  const managerPrompts = [
    'Summarize pending approvals',
    'Explain the ₹25,000 approval rule',
    'What should I check before approving a claim?'
  ];"""

new_manager_prompts = """  const managerPrompts = [
    'Give me a review of claims',
    'Review pending claims',
    'Explain the ₹25,000 approval rule',
    'What should I check before approving a claim?'
  ];"""

if old_manager_prompts in content:
    content = content.replace(old_manager_prompts, new_manager_prompts)
    print("Updated managerPrompts")
else:
    print("Could not match old_manager_prompts directly")

# 2. Update Status component to handle Auto-approved and Declined
old_status = """function Status({ status }) { const cls = status === 'Approved' ? 'approved' : status === 'Rejected' ? 'rejected' : status === 'Needs approval' ? 'pending' : status === 'Blocked' ? 'blocked' : 'submitted'; return <span className={`status ${cls}`}><i></i>{status}</span>; }"""

new_status = """function Status({ status }) {
  const s = (status || '').toLowerCase();
  const cls = s.includes('auto-approved') || s.includes('approved') ? 'approved'
            : s.includes('declin') || s.includes('reject') || s.includes('block') ? 'rejected'
            : s.includes('need') || s.includes('review') || s.includes('pend') ? 'pending'
            : 'submitted';
  return <span className={`status ${cls}`}><i></i>{status}</span>;
}"""

if old_status in content:
    content = content.replace(old_status, new_status)
    print("Updated Status component")
else:
    pattern = r'function Status\(\{ status \}\) \{.*?return <span className=\{`status \$\{cls\}`\}><i></i>\{status\}</span>; \}'
    content = re.sub(pattern, new_status, content, flags=re.DOTALL)
    print("Regex updated Status component")

# 3. Update login claim mapping to distinguish Low risk (Auto-approved), Moderate risk (Needs review), High risk (Declined)
old_login_map = """        const mapped = result.claims.map(c => {
          const firstItem = c.items?.[0] || {};
          const statusMap = {
            PENDING_APPROVAL: 'Needs approval',
            SUBMITTED: 'Submitted',
            APPROVED: 'Approved',
            REJECTED: 'Rejected',
            DRAFT: 'Draft',
          };
          return {
            id: c.id,
            person: c.employee_name || finalName,
            purpose: c.title,
            vendor: firstItem.vendor || '',
            amount: Number(c.total || 0),
            date: (c.created_at || '').slice(0, 10),
            category: firstItem.category || 'Other',
            status: statusMap[c.status] || c.status,
            risk: Number(c.total || 0) > 25000 ? 'High' : 'Low',
            items: c.items?.length || 1,
            initials: (c.employee_name || finalName)
              .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase(),
          };
        });"""

new_login_map = """        const mapped = result.claims.map(c => {
          const firstItem = c.items?.[0] || {};
          const reasonLower = (c.decision_reason || '').toLowerCase();
          const isAutoApproved = (c.status === 'APPROVED' || c.status === 'SUBMITTED') && (reasonLower.includes('auto-approved') || c.risk_level === 'LOW');
          const isDeclined = c.status === 'REJECTED' || reasonLower.includes('declined') || c.risk_level === 'HIGH';
          
          let statusLabel = 'Draft';
          if (isAutoApproved) statusLabel = 'Auto-approved';
          else if (isDeclined) statusLabel = 'Declined';
          else if (c.status === 'PENDING_APPROVAL') statusLabel = 'Needs review';
          else if (c.status === 'APPROVED' || c.status === 'SUBMITTED') statusLabel = 'Approved';

          let riskTier = 'Low';
          if (c.risk_level === 'HIGH' || isDeclined) riskTier = 'High';
          else if (c.risk_level === 'MEDIUM' || Number(c.total || 0) > 25000) riskTier = 'Moderate';

          return {
            id: c.id,
            person: c.employee_name || finalName,
            purpose: c.title,
            vendor: firstItem.vendor || '',
            amount: Number(c.total || 0),
            date: (c.created_at || '').slice(0, 10),
            category: firstItem.category || 'Other',
            status: statusLabel,
            risk: riskTier,
            items: c.items?.length || 1,
            initials: (c.employee_name || finalName)
              .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase(),
            decisionReason: c.decision_reason || '',
            policyReason: c.decision_reason || '',
          };
        });"""

if old_login_map in content:
    content = content.replace(old_login_map, new_login_map)
    print("Updated login mapping")
else:
    print("Could not match old_login_map")

# 4. Update Approvals Component with Risk Triage Filters & Badges
old_approvals_comp = """function Approvals({
  claims,
  approve,
  setSelected,
  chatMessages,
  chat,
  setChat,
  sendChat,
  chatFiles,
  setChatFiles
}) {
  const pendingClaims = claims.filter(
    claim => claim.status === 'Needs approval'
  );

  return (
    <div className="approvals-page">

      <div className="approvals-heading">
        <div>
          <h2>Manager Approvals</h2>
          <p>Review expense claims that require manager approval.</p>
        </div>

        <span className="approval-count">
          {pendingClaims.length} awaiting review
        </span>
      </div>

      <div className="manager-content-grid">

        {/* LEFT: PENDING APPROVALS */}

        <div className="approvals-card">

          <div className="approvals-card-header">
            <div>
              <h3>Pending requests</h3>
              <p>Claims waiting for your decision</p>
            </div>

            <span className="approval-badge">
              {pendingClaims.length} Pending
            </span>
          </div>

          {pendingClaims.length === 0 ? (
            <div className="approvals-empty">
              <h3>All caught up!</h3>
              <p>There are no expense claims waiting for approval.</p>
            </div>
          ) : (
            <div className="approvals-list">

              {pendingClaims.map(claim => (
                <div className="approval-row" key={claim.id}>

                  <div className="approval-vendor">
                    <div className="approval-vendor-icon">₹</div>

                    <div>
                      <h4>{claim.vendor}</h4>
                      <p>{claim.category} · {claim.date}</p>
                      <small>{claim.person} · {claim.id}</small>
                    </div>
                  </div>

                  <div className="approval-amount">
                    <small>Claim amount</small>
                    <strong>
                      ₹{Number(claim.amount).toLocaleString('en-IN')}
                    </strong>
                  </div>

                  <span className="approval-status">
                    Needs approval
                  </span>

                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      className="approval-review-btn"
                      onClick={() => setSelected(claim)}
                    >
                      Review →
                    </button>
                    <button
                      className="approve-button"
                      style={{ padding: '6px 12px', fontSize: '12px' }}
                      onClick={() => approve(claim.id, 'Approved')}
                    >
                      ✓ Approve
                    </button>
                    <button
                      className="reject-button"
                      style={{ padding: '6px 12px', fontSize: '12px' }}
                      onClick={() => approve(claim.id, 'Rejected')}
                    >
                      × Reject
                    </button>
                  </div>

                </div>
              ))}

            </div>
          )}

        </div>

        {/* RIGHT: MANAGER AI ASSISTANT */}

        <AssistantPanel
          chatMessages={chatMessages}
          chat={chat}
          setChat={setChat}
          sendChat={sendChat}
          role="Manager"
          chatFiles={chatFiles}
          setChatFiles={setChatFiles}
        />

      </div>

    </div>
  );
}"""

new_approvals_comp = """function Approvals({
  claims,
  approve,
  setSelected,
  chatMessages,
  chat,
  setChat,
  sendChat,
  chatFiles,
  setChatFiles
}) {
  const [filter, setFilter] = useState('review'); // 'review', 'auto', 'declined', 'all'

  const moderateClaims = claims.filter(
    c => c.status === 'Needs review' || c.status === 'Needs approval' || c.status === 'PENDING_APPROVAL'
  );
  const autoApprovedClaims = claims.filter(
    c => c.status === 'Auto-approved' || (c.status === 'Approved' && c.risk === 'Low')
  );
  const declinedClaims = claims.filter(
    c => c.status === 'Declined' || c.status === 'Rejected' || c.risk === 'High'
  );

  const displayedClaims =
    filter === 'review' ? moderateClaims
    : filter === 'auto' ? autoApprovedClaims
    : filter === 'declined' ? declinedClaims
    : claims;

  return (
    <div className="approvals-page">

      <div className="approvals-heading">
        <div>
          <h2>Manager Governance & Approvals</h2>
          <p>Low risk auto-approved · Moderate risk requires review · High risk declined</p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span className="approval-badge" style={{ background: '#fef3c7', color: '#92400e', borderColor: '#fde68a' }}>
            🟡 {moderateClaims.length} Under review
          </span>
          <span className="approval-badge" style={{ background: '#dcfce7', color: '#166534', borderColor: '#bbf7d0' }}>
            🟢 {autoApprovedClaims.length} Auto-approved
          </span>
          <span className="approval-badge" style={{ background: '#fee2e2', color: '#991b1b', borderColor: '#fecaca' }}>
            🔴 {declinedClaims.length} Declined
          </span>
        </div>
      </div>

      <div className="manager-content-grid">

        {/* LEFT: APPROVALS & RISK TRIAGE LIST */}

        <div className="approvals-card">

          <div className="approvals-card-header" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
              <div>
                <h3>{filter === 'review' ? 'Moderate Risk · Approval Queue'
                     : filter === 'auto' ? 'Low Risk · Auto-Approved Claims'
                     : filter === 'declined' ? 'High Risk · Declined Claims'
                     : 'All Claims Portfolio'}</h3>
                <p>Governed by deterministic policy engine (R1–R10)</p>
              </div>

              <span className="approval-badge">
                {displayedClaims.length} Claims
              </span>
            </div>

            {/* Filter Chips */}
            <div className="filter-row" style={{ margin: 0, padding: 0 }}>
              <button
                type="button"
                className={filter === 'review' ? 'filter-active' : ''}
                onClick={() => setFilter('review')}
              >
                Needs Review ({moderateClaims.length})
              </button>
              <button
                type="button"
                className={filter === 'auto' ? 'filter-active' : ''}
                onClick={() => setFilter('auto')}
              >
                Auto-Approved ({autoApprovedClaims.length})
              </button>
              <button
                type="button"
                className={filter === 'declined' ? 'filter-active' : ''}
                onClick={() => setFilter('declined')}
              >
                Declined ({declinedClaims.length})
              </button>
              <button
                type="button"
                className={filter === 'all' ? 'filter-active' : ''}
                onClick={() => setFilter('all')}
              >
                All ({claims.length})
              </button>
            </div>
          </div>

          {displayedClaims.length === 0 ? (
            <div className="approvals-empty">
              <h3>{filter === 'review' ? 'All caught up!' : 'No claims in this category'}</h3>
              <p>{filter === 'review'
                ? 'There are currently no moderate-risk claims waiting for approval.'
                : 'Claims matching this risk category will appear here.'}</p>
            </div>
          ) : (
            <div className="approvals-list">

              {displayedClaims.map(claim => (
                <div className="approval-row" key={claim.id} style={{ alignItems: 'flex-start' }}>

                  <div className="approval-vendor">
                    <div className="approval-vendor-icon">
                      {claim.risk === 'Low' ? '🟢' : claim.risk === 'Moderate' ? '🟡' : '🔴'}
                    </div>

                    <div>
                      <h4>{claim.vendor || claim.purpose}</h4>
                      <p>{claim.category} · {claim.date}</p>
                      <small>{claim.person} · {claim.id}</small>
                      {claim.decisionReason && (
                        <div style={{ marginTop: '4px', fontSize: '11px', color: '#64748b' }}>
                          {claim.decisionReason}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="approval-amount">
                    <small>Claim amount</small>
                    <strong>
                      ₹{Number(claim.amount).toLocaleString('en-IN')}
                    </strong>
                    <div style={{ marginTop: '4px' }}>
                      <span className={`risk ${claim.risk === 'Moderate' ? 'medium' : claim.risk.toLowerCase()}`}>
                        {claim.risk} Risk
                      </span>
                    </div>
                  </div>

                  <span className="approval-status">
                    <Status status={claim.status} />
                  </span>

                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    <button
                      className="approval-review-btn"
                      onClick={() => setSelected(claim)}
                    >
                      Review →
                    </button>
                    {claim.status === 'Needs review' && (
                      <>
                        <button
                          className="approve-button"
                          style={{ padding: '6px 12px', fontSize: '12px' }}
                          onClick={() => approve(claim.id, 'Approved')}
                        >
                          ✓ Approve
                        </button>
                        <button
                          className="reject-button"
                          style={{ padding: '6px 12px', fontSize: '12px' }}
                          onClick={() => approve(claim.id, 'Rejected')}
                        >
                          × Decline
                        </button>
                      </>
                    )}
                  </div>

                </div>
              ))}

            </div>
          )}

        </div>

        {/* RIGHT: MANAGER AI ASSISTANT */}

        <AssistantPanel
          chatMessages={chatMessages}
          chat={chat}
          setChat={setChat}
          sendChat={sendChat}
          role="Manager"
          chatFiles={chatFiles}
          setChatFiles={setChatFiles}
        />

      </div>

    </div>
  );
}"""

if old_approvals_comp in content:
    content = content.replace(old_approvals_comp, new_approvals_comp)
    print("Updated Approvals component with risk filters and badges")
else:
    print("Could not match old_approvals_comp directly, trying regex")
    pattern = r'function Approvals\(\{.*?export default App;'
    content = re.sub(pattern, new_approvals_comp + "\n\nexport default App;", content, flags=re.DOTALL)
    print("Regex updated Approvals component")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved updated App.jsx")

