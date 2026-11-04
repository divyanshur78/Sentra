import re

path = 'Sentrafrnt/src/App.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update sendChat to allow manager chat and upload attached files
old_send_chat = """const sendChat = async () => {
  if (!chat.trim() && chatFiles.length === 0) return;

  const userMessage = chat.trim() || 'Please review these attached files.';
  const fileNames = chatFiles.map(file => file.name);

  setChatMessages(old => [
    ...old,
    {
      from: 'you',
      text: userMessage,
      files: fileNames
    }
  ]);

  setChat('');
  setChatFiles([]);

  if (role !== 'Employee') {
    setChatMessages(old => [
      ...old,
      {
        from: 'agent',
        text: 'The AI assistant is currently available for employee expense workflows.'
      }
    ]);
    return;
  }

  try {
    const result = await api.chat(userId, userMessage);

    const responseText =
      result.response ||
      result.message ||
      result.answer ||
      'The backend processed your request.';

    setChatMessages(old => [
      ...old,
      {
        from: 'agent',
        text: responseText
      }
    ]);

  } catch (error) {
    console.error('AI chat failed:', error);

    setChatMessages(old => [
      ...old,
      {
        from: 'agent',
        text: `Unable to reach Sentra AI: ${error.message}`
      }
    ]);
  }
};"""

new_send_chat = """const sendChat = async () => {
  if (!chat.trim() && chatFiles.length === 0) return;

  const userMessage = chat.trim() || 'Please review these attached files.';
  const filesToUpload = [...chatFiles];
  const fileNames = filesToUpload.map(file => file.name);

  setChatMessages(old => [
    ...old,
    {
      from: 'you',
      text: userMessage,
      files: fileNames
    }
  ]);

  setChat('');
  setChatFiles([]);

  try {
    let uploadedReceipts = [];
    if (filesToUpload.length > 0 && userId) {
      for (const f of filesToUpload) {
        try {
          const up = await api.uploadReceipt(userId, f);
          if (up.receipts) uploadedReceipts.push(...up.receipts);
        } catch (e) {
          console.warn('Chat receipt upload error:', e);
        }
      }
    }

    let messageToSend = userMessage;
    if (uploadedReceipts.length > 0) {
      const details = uploadedReceipts.map(r =>
        `Receipt: ${r.vendor || 'Unknown'} (₹${r.amount || 0}, ${r.category || 'other'})`
      ).join(', ');
      messageToSend += ` [Attached: ${details}]`;
    }

    const result = await api.chat(userId, messageToSend);

    let responseText =
      result.response ||
      result.message ||
      result.answer ||
      'The backend processed your request.';

    if (uploadedReceipts.length > 0) {
      const r = uploadedReceipts[0];
      responseText += `\\n\\n✓ Parsed receipt: ${r.vendor || 'Vendor'} · ₹${r.amount || '0'} (${r.category || 'expense'}). You can click '+ New claim' to create and submit this claim.`;
    }

    setChatMessages(old => [
      ...old,
      {
        from: 'agent',
        text: responseText
      }
    ]);

  } catch (error) {
    console.error('AI chat failed:', error);

    setChatMessages(old => [
      ...old,
      {
        from: 'agent',
        text: `Unable to reach Sentra AI: ${error.message}`
      }
    ]);
  }
};"""

if old_send_chat in content:
    content = content.replace(old_send_chat, new_send_chat)
    print("Replaced sendChat")
else:
    print("Could not match old_send_chat directly, trying regex")
    pattern = r'const sendChat = async \(\) => \{.*?if \(role !== \'Employee\'\).*?setChatMessages\(old => \[\.\.\.old, \{ from: \'agent\', text: `Unable to reach Sentra AI: \$\{error\.message\}` \} \]\);\s*\}\s*\};'
    content = re.sub(pattern, new_send_chat, content, flags=re.DOTALL)
    print("Regex replaced sendChat")

# 2. Fix receipt ID check in createClaim
old_receipt_id = """    const uploadResult = await api.uploadReceipt(
      userId,
      formData.receipt
    );

    const receipt = uploadResult.receipts?.[0];

    if (!receipt?.id) {
      throw new Error('Receipt upload failed.');
    }

    // 2. Create draft claim
    const draft = await api.createDraft({
      employee_id: userId,
      title: formData.purpose.trim(),
      purpose: formData.notes?.trim() || formData.purpose.trim(),
      items: [
        {
          receipt_id: receipt.id,"""

new_receipt_id = """    const uploadResult = await api.uploadReceipt(
      userId,
      formData.receipt
    );

    const receipt = uploadResult.receipts?.[0];
    const receiptId = receipt?.id || receipt?.receipt_id;

    if (!receiptId) {
      throw new Error('Receipt upload failed.');
    }

    // 2. Create draft claim
    const draft = await api.createDraft({
      employee_id: userId,
      title: formData.purpose.trim(),
      purpose: formData.notes?.trim() || formData.purpose.trim(),
      items: [
        {
          receipt_id: receiptId,"""

if old_receipt_id in content:
    content = content.replace(old_receipt_id, new_receipt_id)
    print("Replaced receiptId check")
else:
    print("Could not match old_receipt_id")

# 3. Add direct approve/reject buttons in Approvals
old_approval_btn = """                  <button
                    className="approval-review-btn"
                    onClick={() => setSelected(claim)}
                  >
                    Review claim →
                  </button>"""

new_approval_btn = """                  <div style={{ display: 'flex', gap: '8px' }}>
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
                  </div>"""

if old_approval_btn in content:
    content = content.replace(old_approval_btn, new_approval_btn)
    print("Replaced approval buttons")
else:
    print("Could not match old_approval_btn")

# 4. Overview dynamic statistics
old_stats = """  const pending = claims.filter(
    c => c.status === 'Needs approval'
  ).length;

  return (
    <>
      <section className="overview-dashboard">
        <div className="overview-left">
          <section className="stats-grid">
            <Stat
              label="Total claimed"
              value="₹86,420"
              delta="12.8%"
              note="vs. last month"
              icon="↗"
              tone="violet"
            />
            <Stat
              label="Awaiting approval"
              value={String(pending + 2).padStart(2, '0')}
              delta="Needs attention"
              note="3 claims in queue"
              icon="◷"
              tone="amber"
            />
            <Stat
              label="Approved this month"
              value="24"
              delta="↑ 8.4%"
              note="vs. last month"
              icon="✓"
              tone="green"
            />
            <Stat
              label="Policy compliance"
              value="98.6%"
              delta="+2.1%"
              note="Excellent control"
              icon="◈"
              tone="blue"
            />
          </section>"""

new_stats = """  const totalAmount = claims.reduce((sum, c) => sum + (Number(c.amount) || 0), 0);
  const pendingCount = claims.filter(c => c.status === 'Needs approval').length;
  const approvedCount = claims.filter(c => c.status === 'Approved' || c.status === 'Submitted').length;
  const blockedCount = claims.filter(c => c.status === 'Blocked' || c.status === 'Rejected').length;
  const compliance = claims.length > 0 ? ((claims.length - blockedCount) / claims.length * 100).toFixed(1) : '100';

  return (
    <>
      <section className="overview-dashboard">
        <div className="overview-left">
          <section className="stats-grid">
            <Stat
              label="Total claimed"
              value={money(totalAmount)}
              delta={`${claims.length} claims`}
              note="Active total"
              icon="↗"
              tone="violet"
            />
            <Stat
              label="Awaiting approval"
              value={String(pendingCount).padStart(2, '0')}
              delta={pendingCount > 0 ? "Needs attention" : "All clear"}
              note={`${pendingCount} pending in queue`}
              icon="◷"
              tone="amber"
            />
            <Stat
              label="Approved / Submitted"
              value={String(approvedCount)}
              delta="Processed"
              note="Compliant claims"
              icon="✓"
              tone="green"
            />
            <Stat
              label="Policy compliance"
              value={`${compliance}%`}
              delta={blockedCount > 0 ? `${blockedCount} blocked` : "Clean"}
              note="Policy adherence"
              icon="◈"
              tone="blue"
            />
          </section>"""

if old_stats in content:
    content = content.replace(old_stats, new_stats)
    print("Replaced overview stats")
else:
    print("Could not match old_stats")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved updated App.jsx")

