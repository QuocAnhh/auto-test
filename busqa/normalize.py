from typing import Any, Dict, List
from datetime import datetime
from dateutil import parser as dtparser
from .models import Message

def _first_present(d: Dict, keys: List[str], default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def normalize_messages(raw: Any) -> List[Message]:
    # Ưu tiên lấy "messages", sau đó đến "data", cuối cùng là list gốc
    if isinstance(raw, dict):
        if isinstance(raw.get("messages"), list):
            items = raw["messages"]
        elif isinstance(raw.get("data"), list):
            items = raw["data"]
        else:
            items = []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []

    out: List[Message] = []
    for i, m in enumerate(items):
        if not isinstance(m, dict):
            continue
        text = _first_present(m, ["content", "text", "message", "body", "payload"], "") or ""
        sender = (_first_present(m, ["role", "sender", "from", "author", "source"], "") or "").lower()
        sender_name = _first_present(m, ["sender_name", "name", "display_name", "fromName"], None)
        ts_raw = _first_present(m, ["ts", "timestamp", "createdAt", "created_at", "time"], None)

        ts = None
        if ts_raw is not None:
            try:
                if isinstance(ts_raw, (int, float)):
                    if ts_raw > 10**12: ts = datetime.fromtimestamp(ts_raw/1000.0)
                    elif ts_raw > 10**10: ts = datetime.fromtimestamp(ts_raw/1000.0)
                    else: ts = datetime.fromtimestamp(ts_raw)
                else:
                    ts = dtparser.parse(str(ts_raw))
            except Exception:
                ts = None

        stype = "unknown"
        if any(k in sender for k in ["agent", "support", "staff", "cskh"]):
            stype = "agent"
        elif any(k in sender for k in ["user", "customer", "khach"]):
            stype = "user"
        elif "system" in sender:
            stype = "system"
        else:
            stype = "user" if i == 0 else "agent"

        out.append(Message(ts=ts, sender_type=stype, sender_name=sender_name, text=str(text).strip()))

    out.sort(key=lambda x: x.ts or datetime.min)
    return out

def build_transcript(messages: List[Message], max_chars: int = 24000) -> str:
    lines = []
    for m in messages:
        ts = m.ts.strftime("%Y-%m-%d %H:%M:%S") if m.ts else "-"
        who = "USER" if m.sender_type == "user" else ("AGENT" if m.sender_type == "agent" else m.sender_type.upper())
        text = (m.text or "").replace("\n", " ").strip()
        lines.append(f"[{ts}] {who}: {text}")
    full = "\n".join(lines)
    if len(full) <= max_chars:
        return full
    head = full[: max_chars // 2]
    tail = full[- max_chars // 2 :]
    return head + "\n...\n" + tail