from typing import List, Optional, Dict, Any
from .models import Message
from .diagnostics import detect_operational_readiness, detect_risk_compliance

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

def compute_additional_metrics(messages: list, brand_policy=None, brand_prompt_text: str = "") -> dict:
    """Compute rule-based metrics without latency, including diagnostics if brand info provided."""
    # repeated_questions: số lần bot hỏi lại cùng một thông tin theo slot
    repeated_keywords = ["điểm đón", "điểm đến", "thời gian", "số điện thoại", "năm sinh", "ngày", "giờ"]
    question_history = {}
    repeated_questions = 0
    for m in messages:
        if getattr(m, 'sender_type', None) == "agent":
            text = (getattr(m, 'text', '') or '').lower()
            for kw in repeated_keywords:
                if kw in text:
                    if kw in question_history and question_history[kw] >= 1:
                        repeated_questions += 1
                    question_history[kw] = question_history.get(kw, 0) + 1

    # agent_user_ratio: tỷ lệ số tin nhắn của bot chia cho số tin nhắn của khách
    agent_count = sum(1 for m in messages if getattr(m, 'sender_type', None) == "agent")
    user_count = sum(1 for m in messages if getattr(m, 'sender_type', None) == "user")
    agent_user_ratio = agent_count / user_count if user_count else None

    # context_resets: số lần bot endcall hoặc tự giới thiệu lại ở giữa phiên
    context_resets = 0
    for i, m in enumerate(messages):
        if getattr(m, 'sender_type', None) == "agent":
            text = (getattr(m, 'text', '') or '').lower()
            if ("kết thúc" in text or "xin chào" in text or "tôi là" in text or "tổng đài viên" in text or "hỗ trợ bạn" in text) and 0 < i < len(messages) - 1:
                context_resets += 1

    # long_option_lists: số lần bot liệt kê danh sách quá dài (nhiều dấu phẩy hoặc mục)
    long_option_lists = 0
    for m in messages:
        if getattr(m, 'sender_type', None) == "agent":
            text = (getattr(m, 'text', '') or '').lower()
            # Đếm số mục phân tách bằng dấu phẩy
            if text.count(",") >= 5 or text.count("\n") >= 5:
                long_option_lists += 1

    # endcall_early_hint: kiểm tra bot kết thúc sớm khi thiếu slot bắt buộc
    endcall_early_hint = 0
    transcript_text = " ".join([getattr(m, 'text', '') for m in messages]).lower()
    
    # Kiểm tra các từ khóa kết thúc cuộc gọi
    early_end_keywords = ["kết thúc", "tạm biệt", "hẹn gặp lại", "cảm ơn bạn đã gọi"]
    has_early_end = any(keyword in transcript_text for keyword in early_end_keywords)
    
    # Kiểm tra thiếu thông tin cơ bản
    basic_info_missing = (
        "điểm đón" not in transcript_text or 
        "điểm đến" not in transcript_text or
        ("ngày" not in transcript_text and "hôm nay" not in transcript_text)
    )
    
    if has_early_end and basic_info_missing:
        endcall_early_hint = 1

    # tts_money_reading_violation: kiểm tra bot đọc số tiền không đúng cách
    tts_money_reading_violation = 0
    for m in messages:
        if getattr(m, 'sender_type', None) == "agent":
            text = (getattr(m, 'text', '') or '').lower()
            # Tìm các số tiền (dạng số + k/đồng)
            import re
            money_patterns = re.findall(r'\d+[k,đ]|\d+\s*(nghìn|ngàn|đồng)', text)
            if money_patterns:
                # Kiểm tra có đọc bằng chữ không
                number_words = ['một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín', 'mười']
                has_word_numbers = any(word in text for word in number_words)
                if not has_word_numbers:
                    tts_money_reading_violation += 1

    result = {
        "repeated_questions": repeated_questions,
        "agent_user_ratio": agent_user_ratio,
        "context_resets": context_resets,
        "long_option_lists": long_option_lists,
        "endcall_early_hint": endcall_early_hint,
        "tts_money_reading_violation": tts_money_reading_violation,
        "policy_violations": 0,  # Will be computed separately when brand_policy is available
    }
    
    # Add diagnostics if brand info is provided
    if brand_policy is not None:
        diagnostics = compute_diagnostics(messages, brand_policy, brand_prompt_text)
        result["diagnostics"] = diagnostics
    
    return result

def detect_policy_violations(messages: list, brand_policy) -> list:
    """Detect policy violations based on brand policy."""
    violations = []
    transcript_text = " ".join([getattr(m, 'text', '') for m in messages if getattr(m, 'sender_type', None) == "agent"]).lower()
    
    # Check phone collection policy
    if brand_policy.forbid_phone_collect:
        phone_keywords = ["số điện thoại", "sđt", "phone", "liên hệ", "gọi lại"]
        if any(keyword in transcript_text for keyword in phone_keywords):
            violations.append("phone_collection_forbidden")
    
    # Check fixed greeting policy
    if brand_policy.require_fixed_greeting:
        first_agent_msg = next((getattr(m, 'text', '') for m in messages if getattr(m, 'sender_type', None) == "agent"), "")
        if not ("chào" in first_agent_msg.lower() and "nhân viên" in first_agent_msg.lower()):
            violations.append("missing_fixed_greeting")
    
    # Check full summary ban
    if brand_policy.ban_full_summary:
        summary_keywords = ["tóm lại", "tổng kết", "như vậy", "để tôi nhắc lại"]
        if any(keyword in transcript_text for keyword in summary_keywords):
            violations.append("full_summary_banned")
    
    return violations

def compute_policy_violations_count(messages: list, brand_policy) -> int:
    """Compute the number of policy violations."""
    violations = detect_policy_violations(messages, brand_policy)
    return len(violations)

def compute_diagnostics(messages: list, brand_policy, brand_prompt_text: str = "") -> dict:
    """Compute diagnostic hits for operational readiness and risk compliance."""
    operational_hits = detect_operational_readiness(messages, brand_policy, brand_prompt_text)
    risk_hits = detect_risk_compliance(messages, brand_policy)
    
    return {
        "operational_readiness": [hit for hit in operational_hits],
        "risk_compliance": [hit for hit in risk_hits]
    }

def filter_non_null_metrics(metrics: dict) -> dict:
    """Remove metrics with None values to avoid including them in prompts."""
    return {k: v for k, v in metrics.items() if v is not None}