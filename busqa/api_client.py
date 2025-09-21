import json
import requests
from typing import Any, Dict

DEFAULT_TIMEOUT = 30

def fetch_messages(base_url: str, conversation_id: str, headers: Dict[str, str] | None = None, timeout: int = DEFAULT_TIMEOUT) -> Any:
    """
    Fetch messages for a single conversation using individual API call.
    
    For bulk processing, consider using tools.bulk_list_evaluate.fetch_conversations_with_messages
    which can fetch multiple conversations in one API call for better performance.
    """
    url = f"{base_url.rstrip('/')}/api/conversations/{conversation_id}/messages"
    r = requests.get(url, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()