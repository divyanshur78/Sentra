const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return response.status === 204 ? null : response.json();
}

export const api = {
  getClaims: () => USE_MOCK ? Promise.resolve(null) : request('/claims'),
  getMetrics: () => USE_MOCK ? Promise.resolve(null) : request('/admin/metrics'),
  runRedTeam: (prompt) => USE_MOCK ? Promise.resolve({ decision: /ignore|override|bypass|another employee|without receipts/i.test(prompt) ? 'DENIED' : 'ALLOWED', reason: 'Demo policy gateway evaluated the request.' }) : request('/redteam/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }) }),
};
