import json

def safe_parse_headers(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        d = json.loads(raw)
        return {str(k): str(v) for k, v in d.items()}
    except Exception:
        return {}