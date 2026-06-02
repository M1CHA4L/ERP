from datetime import datetime
from uuid import uuid4


def generate_number(prefix: str) -> str:
    now = datetime.now()
    suffix = uuid4().hex[:6].upper()
    return f"{prefix}{now:%Y%m%d%H%M%S}{suffix}"
