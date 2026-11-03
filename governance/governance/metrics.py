def build_metrics(audit_store):
    events = audit_store.list_events(limit=1000)
    decisions = [e["payload"] for e in events if e["event_type"] == "policy_decision"]
    attacks = [e["payload"] for e in events if e["event_type"] == "redteam_result"]
    submissions = [e for e in events if e["event_type"] == "claim_submitted"]
    denied = sum(d.get("status") == "DENIED" for d in decisions)
    escalated = sum(d.get("status") == "ESCALATED" for d in decisions)
    allowed = sum(d.get("status") == "ALLOWED" for d in decisions)
    return {
        "total_policy_decisions": len(decisions),
        "allowed": allowed, "denied": denied, "escalated": escalated,
        "policy_block_rate": round((denied / len(decisions)) * 100, 2) if decisions else 0.0,
        "redteam_runs": len(attacks),
        "redteam_blocked": sum(bool(a.get("blocked")) for a in attacks),
        "redteam_pass_rate": round((sum(bool(a.get("passed")) for a in attacks) / len(attacks)) * 100, 2) if attacks else 0.0,
        "unauthorized_submission_count": sum(
            e["payload"].get("authorized") is False for e in submissions
        ),
        "audit_events": len(events),
    }
