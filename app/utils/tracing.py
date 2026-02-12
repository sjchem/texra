
import uuid

def generate_trace_id() -> str:
    return uuid.uuid4().hex[:8]
