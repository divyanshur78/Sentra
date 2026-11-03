"""Shared governance runtime used by the backend adapter and dashboard API."""
import os
from .audit import AuditStore
from .gateway import PolicyGateway
from .redteam import RedTeamRunner

DB_PATH = os.getenv("GOVERNANCE_DB", "./governance_audit.db")
audit_store = AuditStore(DB_PATH)
gateway = PolicyGateway(audit_store)
redteam = RedTeamRunner(gateway, audit_store)
