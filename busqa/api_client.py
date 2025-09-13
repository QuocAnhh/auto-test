import json
import requests
from typing import Any, Dict

DEFAULT_TIMEOUT = 20

def fetch_messages(base_url: str, conversation_id: str, headers: Dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> Any:
    url = f"{base_url.rstrip('/')}/api/conversations/{conversation_id}/messages"
    r = requests.get(url, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()