/** Minimal typed client for Person 2's React/Vite frontend. */
const BASE = (import.meta as any).env?.VITE_API_BASE_URL ?? "http://localhost:8000/api";

export type PolicyStatus = "ALLOWED" | "DENIED" | "ESCALATED";
export interface PolicyDecision {
  decision_id: string; status: PolicyStatus; action: string; rule_ids: string[];
  reason: string; evidence: Record<string, unknown>; risk_level: string;
  recommended_next_step: string; timestamp: string;
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/governance${path}`, {
    ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) throw new Error(`Governance API ${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}
export const governanceApi = {
  decide: (body: unknown) => request<PolicyDecision>("/decision", { method: "POST", body: JSON.stringify(body) }),
  runAttack: (body: unknown) => request<any>("/redteam/run", { method: "POST", body: JSON.stringify(body) }),
  metrics: () => request<any>("/metrics"),
  audit: (limit = 100) => request<any>(`/audit?limit=${limit}`),
  verifyAudit: () => request<any>("/audit/verify"),
  trace: (runId: string) => request<any>(`/trace/${encodeURIComponent(runId)}`),
  scenarios: () => request<any[]>("/redteam/scenarios"),
};

/** Subscribe to live audit/status events. Remember to call the returned cleanup function. */
export function subscribeGovernanceEvents(
  onEvent: (eventType: string, payload: any) => void,
  runId?: string
): () => void {
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  const source = new EventSource(`${BASE}/governance/events${query}`);
  const types = ["policy_decision", "redteam_result", "agent_status", "tool_call_requested",
    "tool_call_result", "human_approval", "claim_submitted", "evaluation_result",
    "draft_created", "submission_blocked", "approval_requested", "manager_approved",
    "manager_rejected", "memory_lookup", "intent_parsed"];
  types.forEach(type => source.addEventListener(type, (event: MessageEvent) => {
    try { onEvent(type, JSON.parse(event.data)); } catch { /* ignore malformed event */ }
  }));
  return () => source.close();
}
