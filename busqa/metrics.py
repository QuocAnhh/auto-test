from typing import List, Optional, Dict, Any
from .models import Message

def compute_latency_metrics(messages: List[Message]) -> Dict[str, Any]:
    first_resp_latency = None
    per_resp = []
    last_user_ts = None
    agent_count = 0
    user_count = 0

    for m in messages:
        if m.sender_type == "user":
            user_count += 1
            last_user_ts = m.ts
        elif m.sender_type == "agent":
            agent_count += 1
            if last_user_ts and m.ts:
                delta = (m.ts - last_user_ts).total_seconds()
                if first_resp_latency is None:
                    first_resp_latency = max(delta, 0)
                per_resp.append(max(delta, 0))

    avg_agent_resp = sum(per_resp)/len(per_resp) if per_resp else None
    total_turns = user_count + agent_count
    duration = None
    if messages and messages[0].ts and messages[-1].ts:
        duration = (messages[-1].ts - messages[0].ts).total_seconds()

    return {
        "first_response_latency_seconds": first_resp_latency,
        "avg_agent_response_latency_seconds": avg_agent_resp,
        "agent_messages": agent_count,
        "user_messages": user_count,
        "total_turns": total_turns,
        "duration_seconds": duration,
    }