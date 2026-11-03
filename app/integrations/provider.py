from app.integrations.local_governance import LocalGovernanceAdapter

# Person 3: replace with Person3GovernanceAdapter when their gateway is ready.
_governance = LocalGovernanceAdapter()

def get_governance():
    return _governance

def set_governance(adapter):
    global _governance
    _governance = adapter
