"""
Tests for diagnostics detection and penalty application
"""
import pytest
from datetime import datetime
from unittest.mock import Mock

from busqa.diagnostics import detect_operational_readiness, detect_risk_compliance
from busqa.evaluator import apply_diagnostics_penalties
from busqa.prompt_loader import load_diagnostics_config


class MockMessage:
    def __init__(self, sender_type, text, ts=None):
        self.sender_type = sender_type
        self.text = text
        self.ts = ts or datetime.now()


class MockBrandPolicy:
    def __init__(self, **kwargs):
        self.forbid_phone_collect = kwargs.get('forbid_phone_collect', False)
        self.no_route_validation = kwargs.get('no_route_validation', False)
        self.pdpa_consent_required = kwargs.get('pdpa_consent_required', False)


def test_forbidden_phone_collect():
    """Test detection of phone collection when policy forbids it"""
    messages = [
        MockMessage("agent", "Chào bạn, em có thể hỗ trợ bạn!"),
        MockMessage("user", "Tôi muốn đặt vé"),
        MockMessage("agent", "Cho em xin số điện thoại của bạn ạ"),
    ]
    
    brand_policy = MockBrandPolicy(forbid_phone_collect=True)
    
    hits = detect_risk_compliance(messages, brand_policy)
    
    # Should detect forbidden phone collect
    phone_hits = [hit for hit in hits if hit['key'] == 'forbidden_phone_collect']
    assert len(phone_hits) == 1
    assert len(phone_hits[0]['evidence']) == 1
    assert 'xin số điện thoại' in phone_hits[0]['evidence'][0]
    
    # Test penalty application
    diagnostics_cfg = load_diagnostics_config()
    diagnostics_hits = {"risk_compliance": hits}
    
    result = {
        "criteria": {
            "policy_compliance": {"score": 80.0, "note": "initial"}
        }
    }
    
    result = apply_diagnostics_penalties(result, diagnostics_cfg, diagnostics_hits)
    
    # Should clamp policy_compliance to 30
    assert result["criteria"]["policy_compliance"]["score"] == 30.0
    assert "forbidden_phone_collect" in result["criteria"]["policy_compliance"]["note"]


def test_child_policy_miss():
    """Test detection of missing child policy when child is present"""
    messages = [
        MockMessage("agent", "Chào bạn!"),
        MockMessage("user", "Tôi muốn đặt vé cho 2 người lớn và 1 bé sinh năm 2020"),
        MockMessage("agent", "Được ạ, bạn đi từ đâu đến đâu?"),
        MockMessage("user", "TPHCM đi Đà Lạt"),
        MockMessage("agent", "Vé người lớn 450k ạ"),
    ]
    
    brand_policy = MockBrandPolicy()
    
    hits = detect_operational_readiness(messages, brand_policy, "")
    
    # Should detect child policy miss
    child_hits = [hit for hit in hits if hit['key'] == 'child_policy_miss']
    assert len(child_hits) == 1
    assert 'sinh năm 2020' in child_hits[0]['evidence'][0]
    
    # Test penalty application
    diagnostics_cfg = load_diagnostics_config()
    diagnostics_hits = {"operational_readiness": hits}
    
    result = {
        "criteria": {
            "knowledge_accuracy": {"score": 85.0, "note": "good"},
            "context_flow_closure": {"score": 75.0, "note": "ok"}
        }
    }
    
    result = apply_diagnostics_penalties(result, diagnostics_cfg, diagnostics_hits)
    
    # Should reduce knowledge_accuracy by 15 and context_flow_closure by 10
    assert result["criteria"]["knowledge_accuracy"]["score"] == 70.0  # 85 - 15
    assert result["criteria"]["context_flow_closure"]["score"] == 65.0  # 75 - 10


def test_handover_sla_missing():
    """Test detection of missing SLA handover when ending A-flow"""
    messages = [
        MockMessage("agent", "Chào bạn!"),
        MockMessage("user", "Tôi muốn đặt vé"),
        MockMessage("agent", "Cảm ơn bạn đã gọi, kết thúc cuộc gọi ạ"),
    ]
    
    brand_policy = MockBrandPolicy()
    
    hits = detect_operational_readiness(messages, brand_policy, "")
    
    # Should detect handover SLA missing
    sla_hits = [hit for hit in hits if hit['key'] == 'handover_sla_missing']
    assert len(sla_hits) == 1
    assert 'kết thúc cuộc gọi' in sla_hits[0]['evidence'][0]
    
    # Test penalty application
    diagnostics_cfg = load_diagnostics_config()
    diagnostics_hits = {"operational_readiness": hits}
    
    result = {
        "criteria": {
            "context_flow_closure": {"score": 80.0, "note": "good"}
        }
    }
    
    result = apply_diagnostics_penalties(result, diagnostics_cfg, diagnostics_hits)
    
    # Should clamp context_flow_closure to 60
    assert result["criteria"]["context_flow_closure"]["score"] == 60.0


def test_fare_math_inconsistent():
    """Test detection of inconsistent fare information"""
    messages = [
        MockMessage("agent", "Chào bạn!"),
        MockMessage("user", "Giá vé TPHCM - Đà Lạt bao nhiêu?"),
        MockMessage("agent", "Giá vé là 450k ạ"),
        MockMessage("user", "Ok"),
        MockMessage("agent", "À, giá vé là 350k thôi ạ"),
    ]
    
    brand_policy = MockBrandPolicy()
    
    hits = detect_operational_readiness(messages, brand_policy, "")
    
    # Should detect fare inconsistency (450k vs 350k = ~22% difference)
    fare_hits = [hit for hit in hits if hit['key'] == 'fare_math_inconsistent']
    assert len(fare_hits) == 1
    assert '450k' in fare_hits[0]['evidence'][0] and '350k' in fare_hits[0]['evidence'][0]
    
    # Test penalty application
    diagnostics_cfg = load_diagnostics_config()
    diagnostics_hits = {"operational_readiness": hits}
    
    result = {
        "criteria": {
            "knowledge_accuracy": {"score": 85.0, "note": "good"}
        }
    }
    
    result = apply_diagnostics_penalties(result, diagnostics_cfg, diagnostics_hits)
    
    # Should clamp knowledge_accuracy to 50
    assert result["criteria"]["knowledge_accuracy"]["score"] == 50.0


def test_promise_hold_seat():
    """Test detection of seat hold promises beyond authority"""
    messages = [
        MockMessage("agent", "Chào bạn!"),
        MockMessage("user", "Còn chỗ không?"),
        MockMessage("agent", "Em giữ chỗ cho bạn rồi ạ, chắc chắn có vé"),
    ]
    
    brand_policy = MockBrandPolicy()
    
    hits = detect_risk_compliance(messages, brand_policy)
    
    # Should detect promise to hold seat
    hold_hits = [hit for hit in hits if hit['key'] == 'promise_hold_seat']
    assert len(hold_hits) == 1
    assert 'giữ chỗ' in hold_hits[0]['evidence'][0] or 'chắc chắn có vé' in hold_hits[0]['evidence'][0]
    
    # Test penalty application  
    diagnostics_cfg = load_diagnostics_config()
    diagnostics_hits = {"risk_compliance": hits}
    
    result = {
        "criteria": {
            "policy_compliance": {"score": 90.0, "note": "excellent"}
        }
    }
    
    result = apply_diagnostics_penalties(result, diagnostics_cfg, diagnostics_hits)
    
    # Should clamp policy_compliance to 30
    assert result["criteria"]["policy_compliance"]["score"] == 30.0


def test_no_fp_when_rules_absent():
    """Test no false positives when rules can't be determined"""
    messages = [
        MockMessage("agent", "Chào bạn, phòng đôi có sẵn ạ"),
        MockMessage("user", "Ok"),
    ]
    
    brand_policy = MockBrandPolicy()
    brand_prompt_text = "General info about bus company"  # No specific room position rules
    
    hits = detect_operational_readiness(messages, brand_policy, brand_prompt_text)
    
    # Should NOT detect double_room_rule_violation when positions can't be extracted
    room_hits = [hit for hit in hits if hit['key'] == 'double_room_rule_violation']
    assert len(room_hits) == 0


def test_multiple_hits_same_criteria():
    """Test multiple diagnostic hits affecting the same criteria"""
    messages = [
        MockMessage("agent", "Cho em xin số điện thoại"),  # forbidden_phone_collect
        MockMessage("user", "0123456789"),
        MockMessage("agent", "Em cam kết giữ chỗ cho bạn"),  # promise_hold_seat
    ]
    
    brand_policy = MockBrandPolicy(forbid_phone_collect=True)
    
    # Get both operational and risk hits
    or_hits = detect_operational_readiness(messages, brand_policy, "")
    rc_hits = detect_risk_compliance(messages, brand_policy)
    
    diagnostics_hits = {
        "operational_readiness": or_hits,
        "risk_compliance": rc_hits
    }
    
    # Should have both types of hits
    phone_hits = [hit for hit in rc_hits if hit['key'] == 'forbidden_phone_collect']
    hold_hits = [hit for hit in rc_hits if hit['key'] == 'promise_hold_seat']
    
    assert len(phone_hits) == 1
    assert len(hold_hits) == 1
    
    # Test penalty application - both should affect policy_compliance
    diagnostics_cfg = load_diagnostics_config()
    
    result = {
        "criteria": {
            "policy_compliance": {"score": 90.0, "note": "excellent"}
        }
    }
    
    result = apply_diagnostics_penalties(result, diagnostics_cfg, diagnostics_hits)
    
    # Should be clamped to 30 (most restrictive clamp_max)
    assert result["criteria"]["policy_compliance"]["score"] == 30.0
    assert "forbidden_phone_collect" in result["criteria"]["policy_compliance"]["note"]
    assert "promise_hold_seat" in result["criteria"]["policy_compliance"]["note"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
