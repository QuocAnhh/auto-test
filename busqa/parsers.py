from typing import Any, Optional


def extract_bot_id(raw: Any) -> Optional[str]:
    """
    Trích xuất bot_id từ API response một cách an toàn.
    
    Hỗ trợ nhiều khả năng schema:
    - raw.get("bot_id") - top-level bot_id
    - raw.get("metadata", {}).get("bot_id") - bot_id trong metadata
    - Tìm trong messages array nếu có
    - Tìm trong sender info của messages
    
    Args:
        raw: Raw response từ API (thường là dict)
        
    Returns:
        Optional[str]: bot_id nếu tìm thấy, None nếu không
    """
    try:
        if not isinstance(raw, dict):
            return None
        
        # Kiểm tra top-level bot_id
        for key in ("bot_id",):
            v = raw.get(key)
            if v:
                return str(v)

        # Kiểm tra trong metadata
        md = raw.get("metadata") or {}
        if isinstance(md, dict):
            v = md.get("bot_id")
            if v:
                return str(v)

        # Scan messages array để tìm bot_id
        msgs = raw.get("messages")
        if isinstance(msgs, list):
            for m in msgs:
                if isinstance(m, dict):
                    # Kiểm tra bot_id trực tiếp trong message
                    v = m.get("bot_id")
                    if v:
                        return str(v)
                    
                    # Kiểm tra trong sender info
                    sender = m.get("sender") or {}
                    if isinstance(sender, dict):
                        v = sender.get("bot_id")
                        if v:
                            return str(v)
        
        # Kiểm tra các trường khác có thể chứa bot info
        for key in ("agent", "thread", "bot", "assistant"):
            obj = raw.get(key)
            if isinstance(obj, dict):
                v = obj.get("bot_id") or obj.get("id")
                if v:
                    return str(v)
        
        return None
        
    except Exception:
        # Fail safely - không để lỗi parsing làm crash toàn bộ evaluation
        return None
