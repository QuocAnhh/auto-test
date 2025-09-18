import re
from typing import List, TypedDict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import itertools


class DiagnosticHit(TypedDict):
    key: str
    evidence: List[str]


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

    with ThreadPoolExecutor() as executor:
        futures = []
        futures.append(executor.submit(_detect_double_room_violation, agent_responses, brand_prompt_text))
        if user_birth_year:
            futures.append(executor.submit(_detect_child_policy_miss, agent_responses, user_birth_year, current_year))
        if hasattr(brand_policy, 'no_route_validation') and brand_policy.no_route_validation:
            futures.append(executor.submit(_detect_pickup_scope_violation, agent_responses))
        futures.append(executor.submit(_detect_fare_math_inconsistent, agent_responses))
        futures.append(executor.submit(_detect_handover_sla_missing, messages, agent_responses))

        for future in futures:
            hits.extend(future.result())
    
    return hits


def detect_risk_compliance(messages, brand_policy) -> List[DiagnosticHit]:
    """phát hiện các vi phạm rủi ro tuân thủ chính sách"""
    agent_responses = []
    for i, msg in enumerate(messages):
        if getattr(msg, 'sender_type', None) == "agent":
            agent_responses.append((i, getattr(msg, 'text', '') or ''))

    with ThreadPoolExecutor() as executor:
        futures = []
        if getattr(brand_policy, 'forbid_phone_collect', False):
            futures.append(executor.submit(_detect_forbidden_phone_collect, agent_responses))
        
        futures.append(executor.submit(_detect_promise_hold_seat, agent_responses))
        futures.append(executor.submit(_detect_payment_policy_violation, agent_responses, brand_policy))
        
        if getattr(brand_policy, 'pdpa_consent_required', False):
            futures.append(executor.submit(_detect_pdpa_consent_missing, agent_responses))

        results = [future.result() for future in futures]
    
    return list(itertools.chain.from_iterable(results))


def _detect_double_room_violation(agent_responses: List[tuple], brand_prompt_text: str) -> List[DiagnosticHit]:
    """phát hiện vi phạm quy định phòng đôi"""
    hits = []
    
    allowed_positions = set()
    if brand_prompt_text:
        position_pattern = r'chỉ bán[^.]*?([A-B]\d[D](?:\s*,\s*[A-B]\d[D])*)'
        matches = re.findall(position_pattern, brand_prompt_text, re.IGNORECASE)
        for match in matches:
            positions = re.findall(r'[A-B]\d[D]', match)
            allowed_positions.update(positions)
    
    if not allowed_positions:
        return hits
    
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in ['phòng đôi', 'phòng 2 người']):
            mentioned_positions = set(re.findall(r'[A-B]\d[D]', text.upper()))
            
            violations = mentioned_positions - allowed_positions
            if violations:
                evidence = f"turn #{turn_idx + 1}: '{text[:100]}...'" if len(text) > 100 else f"turn #{turn_idx + 1}: '{text}'"
                hits.append(DiagnosticHit(
                    key="double_room_rule_violation",
                    evidence=[evidence]
                ))
                break
    
    return hits


def _detect_child_policy_miss(agent_responses: List[tuple], birth_year: int, current_year: int) -> List[DiagnosticHit]:
    """phát hiện thiếu sót trong việc áp dụng chính sách trẻ em"""
    hits = []
    
    child_age = current_year - birth_year
    if child_age >= 10:
        return hits
    
    child_policy_keywords = [
        'trẻ', 'em bé', 'phụ thu', 'không phụ thu', 
        'dưới một mét', 'một mét rưỡi', 'một mét bốn'
    ]
    
    policy_mentioned = False
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in child_policy_keywords):
            policy_mentioned = True
            break
    
    if not policy_mentioned:
        evidence = f"Child age {child_age} detected but no child policy mentioned in agent responses"
        hits.append(DiagnosticHit(
            key="child_policy_miss",
            evidence=[evidence]
        ))
    
    return hits


def _detect_pickup_scope_violation(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """phát hiện vi phạm phạm vi đón khi chính sách cấm nó"""
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
                return hits
    
    return hits


def _detect_fare_math_inconsistent(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """phát hiện vi phạm tính toán giá cả"""
    hits = []
    
    prices = []
    for turn_idx, text in agent_responses:
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
                if 'k' in text.lower() or 'nghìn' in text.lower() or 'ngàn' in text.lower():
                    price_value *= 1000
                prices.append((turn_idx, price_value, text))
    
    if len(prices) >= 2:
        for i in range(len(prices) - 1):
            for j in range(i + 1, len(prices)):
                turn1, price1, text1 = prices[i]
                turn2, price2, text2 = prices[j]
                
                if price1 != price2:
                    diff_percent = abs(price1 - price2) / max(price1, price2)
                    diff_absolute = abs(price1 - price2)
                    
                    if diff_percent > 0.2 or diff_absolute > 100000:
                        evidence1 = f"turn #{turn1 + 1}: '{text1[:50]}...'" if len(text1) > 50 else f"turn #{turn1 + 1}: '{text1}'"
                        evidence2 = f"turn #{turn2 + 1}: '{text2[:50]}...'" if len(text2) > 50 else f"turn #{turn2 + 1}: '{text2}'"
                        
                        hits.append(DiagnosticHit(
                            key="fare_math_inconsistent",
                            evidence=[evidence1, evidence2]
                        ))
                        return hits
    
    return hits


def _detect_handover_sla_missing(messages, agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """phát hiện thiếu cam kết SLA khi chuyển giao"""
    hits = []
    
    # kiểm tra nếu cuộc trò chuyện kết thúc (có mẫu kết thúc cuộc gọi hoặc là tin nhắn cuối cùng)
    if not messages:
        return hits
    
    # tìm kiếm chỉ số A-flow và mẫu kết thúc
    conversation_ended = False
    last_agent_response = None
    
    # tìm agent respone cuối cùng
    for turn_idx, text in reversed(agent_responses):
        last_agent_response = (turn_idx, text)
        break
    
    if not last_agent_response:
        return hits
    
    turn_idx, last_text = last_agent_response
    last_text_lower = last_text.lower()
    
    end_patterns = ['kết thúc', 'tạm biệt', 'cảm ơn đã gọi', 'chúc anh', 'chúc chị']
    conversation_ended = any(pattern in last_text_lower for pattern in end_patterns)
    
    if conversation_ended:
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
    """phát hiện vi phạm chính sách cấm thu thập số điện thoại"""
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
                return hits  # only flag once
    
    return hits


def _detect_promise_hold_seat(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """phát hiện lời hứa giữ chỗ"""
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
                return hits 
    
    return hits


def _detect_payment_policy_violation(agent_responses: List[tuple], brand_policy) -> List[DiagnosticHit]:
    """phát hiện vi phạm chính sách thanh toán"""
    hits = []
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
                return hits  
    
    return hits


def _detect_pdpa_consent_missing(agent_responses: List[tuple]) -> List[DiagnosticHit]:
    """phát hiện thiếu sót trong việc thu thập sự đồng ý PDPA"""
    hits = []
    personal_data_patterns = [
        'họ tên', 'năm sinh', 'địa chỉ', 'cmnd', 'cccd', 'căn cước'
    ]
    
    consent_patterns = [
        'em xin phép', 'được phép lưu thông tin', 'đồng ý cho em', 'cho phép em'
    ]
    
    data_collection_turns = []
    for turn_idx, text in agent_responses:
        text_lower = text.lower()
        if any(pattern in text_lower for pattern in personal_data_patterns):
            data_collection_turns.append((turn_idx, text))
    
    # cho mỗi lần thu thập dữ liệu, kiểm tra xem có sự đồng ý trong các lượt gần đó không
    for turn_idx, text in data_collection_turns:
        consent_found = False
        
        # kiểm tra phản hồi của agent hiện tại và 2 phản hồi tiếp theo để tìm sự đồng ý
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
            return hits 
    
    return hits
