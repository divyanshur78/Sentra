from app.integrations.person3_adapter import Person3GovernanceAdapter

_governance = Person3GovernanceAdapter()


def get_governance():
    return _governance


def set_governance(adapter):
    global _governance
    _governance = adapter
