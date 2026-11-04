
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}/api${path}`, options);

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data?.detail || data?.message || `Request failed (${response.status})`;
    throw new Error(
      typeof detail === 'string' ? detail : JSON.stringify(detail)
    );
  }

  return data;
}

const post = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  // Authentication
  login: (user_id) =>
    request('/auth/login', post({ user_id })),

  getClaims: (requesterId) =>
    request(`/claims?requester_id=${encodeURIComponent(requesterId)}`),

  // Receipt upload
  uploadReceipt: (employeeId, file) => {
    const form = new FormData();
    form.append('files', file);

    return request(
      `/receipts/upload?employee_id=${encodeURIComponent(employeeId)}`,
      { method: 'POST', body: form }
    );
  },

  // Expense claims
  createDraft: (body) =>
    request('/claims/draft', post(body)),

  submitClaim: (claimId, employee_id) =>
    request(
      `/claims/${encodeURIComponent(claimId)}/submit`,
      post({ employee_id, confirmation: true })
    ),

  getClaim: (claimId, requesterId) =>
    request(
      `/claims/${encodeURIComponent(claimId)}?requester_id=${encodeURIComponent(requesterId)}`
    ),

  // Manager decisions
  approveClaim: (claimId, manager_id, reason) =>
    request(
      `/claims/${encodeURIComponent(claimId)}/approve`,
      post({ manager_id, reason })
    ),

  rejectClaim: (claimId, manager_id, reason) =>
    request(
      `/claims/${encodeURIComponent(claimId)}/reject`,
      post({ manager_id, reason })
    ),

  finalizeClaim: (claimId, manager_id) =>
    request(
      `/claims/${encodeURIComponent(claimId)}/finalize`,
      post({ manager_id, reason: 'Manager finalized approved claim' })
    ),

  // AI assistant
  chat: (employee_id, message) =>
    request('/chat', post({ employee_id, message })),

  // Red-team testing
  runRedTeam: (prompt, employee_id = 'emp-001') =>
    request(
      '/redteam/run',
      post({
        employee_id,
        attack_type: 'prompt_injection',
        prompt,
      })
    ),

  // Governance and monitoring
  getMetrics: () =>
    request('/governance/metrics'),

  getAudit: (limit = 100) =>
    request(`/governance/audit?limit=${limit}`),

  verifyAudit: () =>
    request('/governance/audit/verify'),

  getPolicyRules: () =>
    request('/policy/rules'),

  getRedTeamScenarios: () =>
    request('/governance/redteam/scenarios'),

  getGovernanceHealth: () =>
    request('/governance/health'),
};
