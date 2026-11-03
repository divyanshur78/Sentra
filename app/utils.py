import json, uuid
from datetime import datetime, timezone

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"

def dumps(value):
    return json.dumps(value, ensure_ascii=False, default=str)

def loads(value, default=None):
    try:
        return json.loads(value) if value else (default if default is not None else [])
    except (TypeError, json.JSONDecodeError):
        return default if default is not None else []
