export const claims = [
  { id: 'CLM-2048', person: 'Aarav Mehta', initials: 'AM', purpose: 'Bengaluru client visit', date: '04 Nov 2026', amount: 42850, status: 'Needs approval', risk: 'High', items: 4, category: 'Travel' },
  { id: 'CLM-2047', person: 'Riya Sharma', initials: 'RS', purpose: 'Team lunch · Product', date: '03 Nov 2026', amount: 3850, status: 'Submitted', risk: 'Low', items: 2, category: 'Meals' },
  { id: 'CLM-2046', person: 'Kabir Singh', initials: 'KS', purpose: 'Airport transfer', date: '03 Nov 2026', amount: 1250, status: 'Approved', risk: 'Low', items: 1, category: 'Transport' },
  { id: 'CLM-2045', person: 'Ananya Rao', initials: 'AR', purpose: 'Client accommodation', date: '02 Nov 2026', amount: 18200, status: 'Blocked', risk: 'Medium', items: 3, category: 'Lodging' },
];
export const auditEvents = [
  { time: '10:42:18', title: 'Policy decision · ESCALATED', detail: 'CLM-2048 exceeded the ₹25,000 auto-approval threshold.', type: 'warn' },
  { time: '10:42:16', title: 'Receipt extraction completed', detail: '4 receipts processed · 98.2% average confidence.', type: 'good' },
  { time: '10:42:11', title: 'Employee request received', detail: 'Aarav Mehta started a Bengaluru client-visit claim.', type: 'info' },
  { time: '10:39:04', title: 'Prompt injection blocked', detail: 'Receipt instruction was treated as untrusted content.', type: 'danger' },
];
