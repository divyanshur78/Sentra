path = 'Sentrafrnt/src/App.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """const sendChat = async () => {
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

replacement = """const sendChat = async () => {
  if (!chat.trim() && chatFiles.length === 0) return;

  const userMessage = chat.trim() || 'Please process and submit my expense claim with these attached receipts.';
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
    let uploadedReceiptIds = [];
    if (filesToUpload.length > 0 && userId) {
      showToast('Uploading & analyzing receipts...');
      for (const f of filesToUpload) {
        try {
          const up = await api.uploadReceipt(userId, f);
          if (up.receipts) {
            for (const r of up.receipts) {
              const rid = r.id || r.receipt_id;
              if (rid) uploadedReceiptIds.push(rid);
            }
          }
        } catch (e) {
          console.warn('Chat receipt upload error:', e);
        }
      }
    }

    const result = await api.chat(
      userId,
      userMessage,
      uploadedReceiptIds.length > 0 ? uploadedReceiptIds : null,
      true
    );

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

    // If a claim was automatically drafted and submitted, add it immediately to claims state
    if (result.claim) {
      const backendClaim = result.claim;
      const firstItem = backendClaim.items?.[0] || {};
      const statusMap = {
        PENDING_APPROVAL: 'Needs approval',
        SUBMITTED: 'Submitted',
        APPROVED: 'Approved',
        REJECTED: 'Rejected',
        DRAFT: result.policy?.decision === 'DENIED' ? 'Blocked' : 'Draft'
      };

      const newClaim = {
        id: backendClaim.id,
        person: userName,
        purpose: backendClaim.title || userMessage,
        vendor: firstItem.vendor || 'Expense',
        amount: Number(backendClaim.total || 0),
        date: firstItem.date || new Date().toISOString().split('T')[0],
        category: firstItem.category || 'Other',
        status: statusMap[backendClaim.status] || backendClaim.status,
        risk: Number(backendClaim.total || 0) > 25000 ? 'High' : 'Low',
        items: backendClaim.items?.length || 1,
        initials: userName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase(),
        policyReason: result.message
      };

      setClaims(old => [newClaim, ...old.filter(c => c.id !== newClaim.id)]);
      setSelected(newClaim);
      showToast(
        backendClaim.status === 'PENDING_APPROVAL'
          ? `Claim ${newClaim.id} routed for Manager Approval (Rule R6)`
          : backendClaim.status === 'SUBMITTED'
            ? `Claim ${newClaim.id} verified & submitted to ERP!`
            : `Claim ${newClaim.id} saved as draft`
      );
    }

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

if target in content:
    content = content.replace(target, replacement)
    print("Replaced sendChat successfully")
else:
    print("Target not found directly, checking normalization")
    target_clean = target.replace('\r\n', '\n')
    content_clean = content.replace('\r\n', '\n')
    if target_clean in content_clean:
        content_clean = content_clean.replace(target_clean, replacement.replace('\r\n', '\n'))
        content = content_clean
        print("Replaced with newline normalization")
    else:
        print("Failed to replace sendChat")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Saved App.jsx")

