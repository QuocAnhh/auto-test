import re
from typing import List, TypedDict
from datetime import datetime


class DiagnosticHit(TypedDict):
    key: str
    evidence: List[str]  # trích câu/turn cụ thể


def detect_operational_readiness(messages, brand_policy, brand_prompt_text: str) -> List[DiagnosticHit]:
    hits = []
    
    current_year = datetime.now().year
    
    user_birth_year = None
    agent_responses = []
    
    for i, msg in enumerate(messages):
        if getattr(msg, 'sender_type', None) == "agent":
            agent_responses.append((i, getattr(msg, 'text', '') or ''))
        elif getattr(msg, 'sender_type', None) == "user":
            user_text = (getattr(msg, 'text', '') or '').lower()
            birth_year_match = re.search(r'(sinh năm |năm sinh |20(1|2)\d)', user_text)
            if birth_year_match:
                year_match = re.search(r'20(1|2)\d', user_text)
                if year_match:
                    user_birth_year = int(year_match.group())
    
    # 1. double_room_rule_violation
    hits.extend(_detect_double_room_violation(agent_responses, brand_prompt_text))
    
    # 2. child_policy_miss
    if user_birth_year:
        hits.extend(_detect_child_policy_miss(agent_responses, user_birth_year, current_year))
    
    # 3. pickup_scope_violation
    if hasattr(brand_policy, 'no_route_validation') and brand_policy.no_route_validation:
        hits.extend(_detect_pickup_scope_violation(agent_responses))
    
    # 4. fare_math_inconsistent
    hits.extend(_detect_fare_math_inconsistent(agent_responses))
    
    # 5. handover_sla_missing
    hits.extend(_detect_handover_sla_missing(messages, agent_responses))
    
    return hits


def detect_risk_compliance(messages, brand_policy) -> List[DiagnosticHit]:
    """Detect risk compliance issues from conversation."""
    hits = []
    
    agent_responses = []
    for i, msg in enumerate(messages):
        if getattr(msg, 'sender_type', None) == "agent":
            agent_responses.append((i, getattr(msg, 'text', '') or ''))
    
    # 1. forbidden_phone_collect
    if getattr(brand_policy, 'forbid_phone_collect', False):
        hits.extend(_detect_forbidden_phone_collect(agent_responses))
    
    # 2. promise_hold_seat
    hits.extend(_detect_promise_hold_seat(agent_responses))
    
    # 3. payment_policy_violation
    hits.extend(_detect_payment_policy_violation(agent_responses, brand_policy))
    
    # 4. pdpa_consent_missing
    if getattr(brand_policy, 'pdpa_consent_required', False):
        hits.extend(_detect_pdpa_consent_missing(agent_responses))
    
    return hits


def _detect_double_room_violation(agent_responses: List[tuple], brand_prompt_text: str) -> List[DiagnosticHit]:
    """Detect double room rule violations."""
    hits = []
    
    # Extract allowed positions from brand prompt
    allowed_positions = set()
    if brand_prompt_text:
        # Look for patterns like "chỉ bán" followed by position codes
        position_pattern = r'chỉ bán[^.]*?([A-B]\d[D](?:\s*,\s*[A-B]\d[D])*)'
        matches = re.findall(position_pattern, brand_prompt_text, re.IGNORECASE)
        for match in matches:
            # Extract individual position codes
            positions = re.findall(r'[A-B]\d[D]', match)
            allowed_positions.update(positions)
    
    # If no allowed positions found in prompt, skip detection to avoid false positives
    if not allowed_positions:
        return hits
    
    # Check agent responses for double room mentions
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in ['phòng đôi', 'phòng 2 người']):
            # Look for position codes in this response
            mentioned_positions = set(re.findall(r'[A-B]\d[D]', text.upper()))
            
            # Check if any mentioned position is not in allowed list
            violations = mentioned_positions - allowed_positions
            if violations:
                evidence = f"turn #{turn_idx + 1}: '{text[:100]}...'" if len(text) > 100 else f"turn #{turn_idx + 1}: '{text}'"
                hits.append(DiagnosticHit(
                    key="double_room_rule_violation",
                    evidence=[evidence]
                ))
                break  # Only flag once per conversation
    
    return hits


def _detect_child_policy_miss(agent_responses: List[tuple], birth_year: int, current_year: int) -> List[DiagnosticHit]:
    """Detect missing child policy application."""
    hits = []
    
    child_age = current_year - birth_year
    if child_age >= 10:
        return hits  # Not a child, no violation
    
    # Look for child policy keywords in agent responses after birth year mention
    child_policy_keywords = [
        'trẻ', 'em bé', 'phụ thu', 'không phụ thu', 
        'dưới một mét', 'một mét rưỡi', 'một mét bốn'
    ]
    
    # Check if any agent response mentions child policy
    policy_mentioned = False
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in child_policy_keywords):
            policy_mentioned = True
            break
    
    if not policy_mentioned:
        # Find evidence of child age but no policy mention
        evidence = f"Child age {child_age} detected but no child policy mentioned in agent responses"
        hits.append(DiagnosticHit(
            key="child_policy_miss",
            evidence=[evidence]
        ))
    
    return hits


def _detect_pickup_scope_violation(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """Detect pickup scope validation when policy forbids it."""
    hits = []
    
    violation_patterns = [
        'có thuộc tuyến', 'có đón ở', 'không chạy tuyến', 
        'không qua', 'thuộc tuyến không', 'đón ở đó không'
    ]
    
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        for pattern in violation_patterns:
            if pattern in text_lower:
                evidence = f"turn #{turn_idx + 1}: '{text[:100]}...'" if len(text) > 100 else f"turn #{turn_idx + 1}: '{text}'"
                hits.append(DiagnosticHit(
                    key="pickup_scope_violation",
                    evidence=[evidence]
                ))
                return hits  # Only flag once
    
    return hits


def _detect_fare_math_inconsistent(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """Detect inconsistent fare information."""
    hits = []
    
    # Extract all price mentions
    prices = []
    for turn_idx, text in agent_responses:
        # Find prices in various formats
        price_patterns = [
            r'(\d+)k(?:\s|$)',
            r'(\d+)\s*nghìn',
            r'(\d+)\s*ngàn',
            r'(\d+)\s*đồng'
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text.lower())
            for match in matches:
                price_value = int(match)
                # Convert k/nghìn/ngàn to actual value
                if 'k' in text.lower() or 'nghìn' in text.lower() or 'ngàn' in text.lower():
                    price_value *= 1000
                prices.append((turn_idx, price_value, text))
    
    # Check for significant price differences
    if len(prices) >= 2:
        for i in range(len(prices) - 1):
            for j in range(i + 1, len(prices)):
                turn1, price1, text1 = prices[i]
                turn2, price2, text2 = prices[j]
                
                # Check if prices differ significantly
                if price1 != price2:
                    diff_percent = abs(price1 - price2) / max(price1, price2)
                    diff_absolute = abs(price1 - price2)
                    
                    # Flag if >20% difference or >100k absolute difference
                    if diff_percent > 0.2 or diff_absolute > 100000:
                        evidence1 = f"turn #{turn1 + 1}: '{text1[:50]}...'" if len(text1) > 50 else f"turn #{turn1 + 1}: '{text1}'"
                        evidence2 = f"turn #{turn2 + 1}: '{text2[:50]}...'" if len(text2) > 50 else f"turn #{turn2 + 1}: '{text2}'"
                        
                        hits.append(DiagnosticHit(
                            key="fare_math_inconsistent",
                            evidence=[evidence1, evidence2]
                        ))
                        return hits  # Only flag once
    
    return hits


def _detect_handover_sla_missing(messages, agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """Detect missing handover SLA in A-flow."""
    hits = []
    
    # Check if conversation ends (has endcall pattern or is last message)
    if not messages:
        return hits
    
    # Look for A-flow indicators and end patterns
    conversation_ended = False
    last_agent_response = None
    
    # Find the last agent response
    for turn_idx, text in reversed(agent_responses):
        last_agent_response = (turn_idx, text)
        break
    
    if not last_agent_response:
        return hits
    
    turn_idx, last_text = last_agent_response
    last_text_lower = last_text.lower()
    
    # Check for end-of-call patterns
    end_patterns = ['kết thúc', 'tạm biệt', 'cảm ơn đã gọi', 'chúc anh', 'chúc chị']
    conversation_ended = any(pattern in last_text_lower for pattern in end_patterns)
    
    if conversation_ended:
        # Check for SLA handover keywords
        sla_keywords = ['nhân viên gọi lại', 'kết bạn zalo', 'xác nhận sớm', 'lưu ý']
        sla_mentioned = any(keyword in last_text_lower for keyword in sla_keywords)
        
        if not sla_mentioned:
            evidence = f"turn #{turn_idx + 1}: '{last_text[:100]}...'" if len(last_text) > 100 else f"turn #{turn_idx + 1}: '{last_text}'"
            hits.append(DiagnosticHit(
                key="handover_sla_missing",
                evidence=[evidence]
            ))
    
    return hits


def _detect_forbidden_phone_collect(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """Detect phone number collection when forbidden."""
    hits = []
    
    phone_collection_patterns = [
        'số điện thoại', 'cho em xin số', 'đọc số', 
        'liên hệ qua số nào', 'số máy', 'số phone'
    ]
    
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        for pattern in phone_collection_patterns:
            if pattern in text_lower:
                evidence = f"turn #{turn_idx + 1}: '{text[:100]}...'" if len(text) > 100 else f"turn #{turn_idx + 1}: '{text}'"
                hits.append(DiagnosticHit(
                    key="forbidden_phone_collect",
                    evidence=[evidence]
                ))
                return hits  # Only flag once
    
    return hits


def _detect_promise_hold_seat(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """Detect unauthorized seat holding promises."""
    hits = []
    
    promise_patterns = [
        'giữ chỗ', 'đã giữ', 'chắc chắn có vé', 
        'đặt xong rồi', 'em cam kết', 'đã đặt'
    ]
    
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        for pattern in promise_patterns:
            if pattern in text_lower:
                evidence = f"turn #{turn_idx + 1}: '{text[:100]}...'" if len(text) > 100 else f"turn #{turn_idx + 1}: '{text}'"
                hits.append(DiagnosticHit(
                    key="promise_hold_seat",
                    evidence=[evidence]
                ))
                return hits  # Only flag once
    
    return hits


def _detect_payment_policy_violation(agent_responses: List[tuple], brand_policy) -> List[DiagnosticHit]:
    """Detect payment policy violations."""
    hits = []
    
    # This is simplified - in reality, you'd check brand_prompt_text for payment policies
    # For now, we'll look for common deposit/payment violations
    violation_patterns = [
        'đặt cọc', 'cọc', 'trả sau', 'giữ chỗ bằng cọc', 
        'thanh toán sau', 'trả tiền sau'
    ]
    
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        for pattern in violation_patterns:
            if pattern in text_lower:
                evidence = f"turn #{turn_idx + 1}: '{text[:100]}...'" if len(text) > 100 else f"turn #{turn_idx + 1}: '{text}'"
                hits.append(DiagnosticHit(
                    key="payment_policy_violation",
                    evidence=[evidence]
                ))
                return hits  # Only flag once
    
    return hits


def _detect_pdpa_consent_missing(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """Detect missing PDPA consent when collecting personal data."""
    hits = []
    
    # Look for personal data collection
    personal_data_patterns = [
        'họ tên', 'năm sinh', 'địa chỉ', 'cmnd', 'cccd', 'căn cước'
    ]
    
    consent_patterns = [
        'em xin phép', 'được phép lưu thông tin', 'đồng ý cho em', 'cho phép em'
    ]
    
    # Find data collection requests
    data_collection_turns = []
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in personal_data_patterns):
            data_collection_turns.append((turn_idx, text))
    
    # For each data collection, check if consent was given in nearby turns
    for turn_idx, text in data_collection_turns:
        consent_found = False
        
        # Check current and next 2 agent responses for consent
        for check_idx, check_text in agent_responses:
            if check_idx >= turn_idx and check_idx <= turn_idx + 2:
                if any(pattern in check_text.lower() for pattern in consent_patterns):
                    consent_found = True
                    break
        
        if not consent_found:
            evidence = f"turn #{turn_idx + 1}: '{text[:100]}...'" if len(text) > 100 else f"turn #{turn_idx + 1}: '{text}'"
            hits.append(DiagnosticHit(
                key="pdpa_consent_missing",
                evidence=[evidence]
            ))
            return hits  # Only flag once
    
    return hits
