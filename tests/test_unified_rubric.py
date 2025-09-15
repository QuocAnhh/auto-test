import pytest
import yaml
from busqa.prompt_loader import load_unified_rubrics
from busqa.evaluator import ensure_full_criteria, recompute_total, label_from_score, coerce_llm_json_unified
from busqa.metrics import compute_additional_metrics, compute_policy_violations_count
from busqa.brand_specs import BrandPolicy
from busqa.models import Message

def test_unified_rubrics_config():
    """Test that unified rubrics configuration is valid."""
    rubrics_cfg = load_unified_rubrics()
    
    # Check version
    assert rubrics_cfg["version"] == "v1.0"
    
    # Check criteria weights sum to 1.0
    total_weight = sum(rubrics_cfg["criteria"].values())
    assert abs(total_weight - 1.0) < 0.01, f"Total weight {total_weight} should be close to 1.0"
    
    # Check all 8 criteria are present
    expected_criteria = [
        "intent_routing", "slots_completeness", "no_redundant_questions",
        "knowledge_accuracy", "context_flow_closure", "style_tts",
        "policy_compliance", "empathy_experience"
    ]
    for criterion in expected_criteria:
        assert criterion in rubrics_cfg["criteria"], f"Missing criterion: {criterion}"
    
    # Check labels have proper thresholds
    labels = rubrics_cfg["labels"]
    assert len(labels) >= 5
    assert labels[0]["threshold"] == 90  # Xuất sắc
    assert labels[-1]["threshold"] == 0  # Kém

def test_ensure_full_criteria():
    """Test that missing criteria are filled with score=0."""
    rubrics_cfg = load_unified_rubrics()
    
    # Partial result missing some criteria
    partial_result = {
        "criteria": {
            "intent_routing": {"score": 80, "note": "Good routing"},
            "slots_completeness": {"score": 70, "note": "Missing some slots"}
            # Missing other 6 criteria
        }
    }
    
    full_criteria = ensure_full_criteria(partial_result, rubrics_cfg)
    
    # Should have all 8 criteria
    assert len(full_criteria) == 8
    
    # Existing criteria should be preserved
    assert full_criteria["intent_routing"]["score"] == 80
    assert full_criteria["slots_completeness"]["score"] == 70
    
    # Missing criteria should have score=0
    assert full_criteria["knowledge_accuracy"]["score"] == 0.0
    assert full_criteria["knowledge_accuracy"]["note"] == "missing"

def test_recompute_total_score():
    """Test total score calculation using unified weights."""
    rubrics_cfg = load_unified_rubrics()
    
    result = {
        "criteria": {
            "intent_routing": {"score": 80},
            "slots_completeness": {"score": 90},
            "no_redundant_questions": {"score": 70},
            "knowledge_accuracy": {"score": 85},
            "context_flow_closure": {"score": 80},
            "style_tts": {"score": 75},
            "policy_compliance": {"score": 90},
            "empathy_experience": {"score": 80}
        }
    }
    
    total = recompute_total(result, rubrics_cfg)
    
    # Manual calculation
    expected = (80 * 0.15 + 90 * 0.25 + 70 * 0.15 + 85 * 0.15 + 
                80 * 0.15 + 75 * 0.10 + 90 * 0.03 + 80 * 0.02)
    
    assert abs(total - expected) < 0.1

def test_label_from_score():
    """Test label assignment based on score."""
    rubrics_cfg = load_unified_rubrics()
    
    assert label_from_score(95, rubrics_cfg) == "Xuất sắc"
    assert label_from_score(85, rubrics_cfg) == "Tốt"
    assert label_from_score(70, rubrics_cfg) == "Đạt"
    assert label_from_score(55, rubrics_cfg) == "Cần cải thiện"
    assert label_from_score(30, rubrics_cfg) == "Kém"

def test_policy_violations():
    """Test policy violation detection."""
    # Create brand policy that forbids phone collection
    brand_policy = BrandPolicy(forbid_phone_collect=True)
    
    # Messages where agent asks for phone number
    messages = [
        Message(sender_type="user", text="Tôi muốn đặt vé"),
        Message(sender_type="agent", text="Cho em xin số điện thoại của anh để liên hệ"),
        Message(sender_type="user", text="0901234567")
    ]
    
    violations_count = compute_policy_violations_count(messages, brand_policy)
    assert violations_count > 0

def test_different_brands_same_criteria():
    """Test that different brands use the same 8 criteria."""
    rubrics_cfg = load_unified_rubrics()
    
    # Mock LLM output
    llm_output = {
        "version": "v1.0",
        "detected_flow": "A",
        "confidence": 0.8,
        "criteria": {
            "intent_routing": {"score": 80, "note": "Good routing turn 1"},
            "slots_completeness": {"score": 70, "note": "Missing pickup turn 2"},
            "knowledge_accuracy": {"score": 85, "note": "Accurate info turn 3"}
            # Only 3 out of 8 criteria provided
        },
        "total_score": 75,
        "label": "Đạt",
        "final_comment": "Overall decent performance"
    }
    
    # Test with brand 1 policy
    brand1_policy = BrandPolicy(forbid_phone_collect=True, read_money_in_words=True)
    
    result1 = coerce_llm_json_unified(
        llm_output, 
        rubrics_cfg=rubrics_cfg, 
        brand_policy=brand1_policy
    )
    
    # Test with brand 2 policy  
    brand2_policy = BrandPolicy(forbid_phone_collect=False, require_fixed_greeting=True)
    
    result2 = coerce_llm_json_unified(
        llm_output,
        rubrics_cfg=rubrics_cfg,
        brand_policy=brand2_policy
    )
    
    # Both should have exactly 8 criteria
    assert len(result1.criteria) == 8
    assert len(result2.criteria) == 8
    
    # Both should have the same criteria keys
    assert set(result1.criteria.keys()) == set(result2.criteria.keys())
    
    # The criteria should be the unified set
    expected_criteria = set(rubrics_cfg["criteria"].keys())
    assert set(result1.criteria.keys()) == expected_criteria

def test_early_endcall_penalty():
    """Test that early endcall detection applies penalties."""
    rubrics_cfg = load_unified_rubrics()
    
    # Messages with early endcall (missing required slots)
    messages = [
        Message(sender_type="user", text="Tôi muốn đặt vé"),
        Message(sender_type="agent", text="Cảm ơn anh đã gọi, chúc anh ngày tốt lành")
    ]
    
    transcript = "USER: Tôi muốn đặt vé\nAGENT: Cảm ơn anh đã gọi, chúc anh ngày tốt lành"
    
    metrics = compute_additional_metrics(messages)
    
    # Should detect early endcall
    assert metrics["endcall_early_hint"] > 0
    
    # LLM output with high context_flow_closure score
    llm_output = {
        "version": "v1.0",
        "detected_flow": "A",
        "confidence": 0.8,
        "criteria": {
            "context_flow_closure": {"score": 90, "note": "Good closure"}
        },
        "total_score": 80,
        "label": "Tốt"
    }
    
    result = coerce_llm_json_unified(
        llm_output,
        rubrics_cfg=rubrics_cfg,
        messages=messages,
        transcript=transcript,
        metrics=metrics
    )
    
    # context_flow_closure should be penalized
    assert result.criteria["context_flow_closure"]["score"] < 90
    assert "Early end call detected" in result.criteria["context_flow_closure"]["note"]

def test_money_reading_violation():
    """Test TTS money reading violation detection and penalty."""
    rubrics_cfg = load_unified_rubrics()
    
    # Messages where agent reads money incorrectly
    messages = [
        Message(sender_type="user", text="Giá vé bao nhiều?"),
        Message(sender_type="agent", text="Giá vé là 250k anh ạ")  # Should be "hai trăm năm mươi nghìn"
    ]
    
    metrics = compute_additional_metrics(messages)
    
    # Should detect TTS violation
    assert metrics["tts_money_reading_violation"] > 0
    
    llm_output = {
        "version": "v1.0", 
        "detected_flow": "G",
        "confidence": 0.8,
        "criteria": {
            "style_tts": {"score": 90, "note": "Good style"}
        },
        "total_score": 85,
        "label": "Tốt"
    }
    
    result = coerce_llm_json_unified(
        llm_output,
        rubrics_cfg=rubrics_cfg,
        messages=messages,
        transcript="USER: Giá vé bao nhiều?\nAGENT: Giá vé là 250k anh ạ",
        metrics=metrics
    )
    
    # style_tts should be penalized
    assert result.criteria["style_tts"]["score"] < 90
    assert "Money reading violation" in result.criteria["style_tts"]["note"]

if __name__ == "__main__":
    pytest.main([__file__])
