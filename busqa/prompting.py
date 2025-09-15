import json
from .prompt_loader import get_criteria_descriptions

def build_system_prompt_unified(rubrics_cfg: dict, brand_policy, brand_prompt_text: str) -> str:
    """Build unified system prompt with 8 fixed criteria."""
    criteria_desc = get_criteria_descriptions()
    criteria_list = []
    
    for criterion, weight in rubrics_cfg['criteria'].items():
        desc = criteria_desc.get(criterion, "")
        criteria_list.append(f"- **{criterion}** ({weight:.2%}): {desc}")
    
    criteria_text = "\n".join(criteria_list)
    
    # Build policy summary
    policy_bullets = []
    if brand_policy.forbid_phone_collect:
        policy_bullets.append("• KHÔNG được thu thập số điện thoại khách hàng")
    if brand_policy.require_fixed_greeting:
        policy_bullets.append("• BẮT BUỘC chào hỏi theo mẫu cố định")
    if brand_policy.ban_full_summary:
        policy_bullets.append("• KHÔNG được tóm lại toàn bộ cuộc gọi")
    if brand_policy.max_prompted_openers <= 1:
        policy_bullets.append("• GIỚI HẠN số lần gợi ý mở đầu")
    if brand_policy.read_money_in_words:
        policy_bullets.append("• BẮT BUỘC đọc số tiền bằng chữ")
    
    policy_text = "\n".join(policy_bullets) if policy_bullets else "• Không có policy đặc biệt"
    
    return f"""
Bạn là QA Lead đánh giá chất lượng cuộc gọi khách hàng. Sử dụng **BỘ TIÊU CHÍ CHUNG** (8 tiêu chí cố định) cho mọi nhà xe.

## TIÊU CHÍ ĐÁNH GIÁ (8 TIÊU CHÍ CHUNG)
{criteria_text}

## POLICY CỦA BRAND
{policy_text}

## TRI THỨC & FLOW CỦA BRAND
{brand_prompt_text}

## NGUYÊN TẮC CHẤM ĐIỂM
- Chấm từ 0-100 cho từng tiêu chí, tổng điểm = Σ(trọng số × điểm)
- 50 = đạt tối thiểu; 80 = tốt; 90+ = xuất sắc; 100 = hoàn hảo
- Chấm năng lực AGENT, KHÔNG chấm hành vi khách hàng
- Nếu vi phạm policy → hạ điểm policy_compliance và context_flow_closure
- Trả về **JSON THUẦN** (không kèm văn bản khác)
- Note phải kèm **bằng chứng + turn** cụ thể
- Ngôn ngữ: tiếng Việt, súc tích, cụ thể
"""

def get_unified_json_schema(rubrics_cfg: dict) -> dict:
    """Get JSON schema for unified rubric system."""
    flow_types = list(rubrics_cfg.get('flows_slots', {}).keys())
    label_names = [label['label'] for label in rubrics_cfg.get('labels', [])]
    
    return {
        "type": "object",
        "required": ["version", "detected_flow", "confidence", "criteria", "total_score", "label", "final_comment"],
        "properties": {
            "version": {"type": "string"},
            "detected_flow": {"type": "string", "enum": flow_types},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "criteria": {"type": "object"},
            "total_score": {"type": "number", "minimum": 0, "maximum": 100},
            "label": {"type": "string", "enum": label_names},
            "final_comment": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "suggestions": {"type": "array", "items": {"type": "string"}}
        },
        "additionalProperties": True
    }

def build_user_instruction(metrics: dict, transcript: str, rubrics_cfg: dict) -> str:
    """Build user instruction with unified criteria."""
    json_schema = get_unified_json_schema(rubrics_cfg)
    flow_types = list(rubrics_cfg.get('flows_slots', {}).keys())
    criteria_names = list(rubrics_cfg['criteria'].keys())
    
    user_template = """
DỮ LIỆU ĐẦU VÀO
---------------
[Metrics]
{metrics_json}

[Diagnostics] (Tham khảo - đã phát hiện tự động)
{diagnostics_json}

[Transcript - dạng dòng]  
{transcript}

YÊU CẦU ĐẦU RA (JSON)
----------------------
Tuân thủ JSON Schema (mô tả, KHÔNG cần trả lại schema):
{json_schema_desc}

QUY TẮC BẮT BUỘC:
- 'detected_flow': chọn 1 trong {flow_types}
- 'criteria': PHẢI có đủ 8 key: {criteria_names}
- Mỗi tiêu chí: {{"score": 0-100, "note": "bằng chứng + turn cụ thể"}}
- Note phải nêu rõ turn và trích dẫn bằng chứng (ví dụ: "turn #3: 'agent nói...'")
- Diagnostics chỉ tham khảo, không bắt buộc trùng kết quả
- 'total_score': tính theo trọng số đã cho
- 'label': theo ngưỡng đã định
- 'suggestions': LUÔN LUÔN cung cấp 2-3 đề xuất cải thiện (bất kể điểm số)
"""
    
    # Extract diagnostics from metrics if available
    diagnostics = metrics.get("diagnostics", {"operational_readiness": [], "risk_compliance": []})
    
    return user_template.format(
        metrics_json=json.dumps({k: v for k, v in metrics.items() if k != "diagnostics"}, ensure_ascii=False, indent=2),
        diagnostics_json=json.dumps(diagnostics, ensure_ascii=False, indent=2),
        transcript=transcript,
        json_schema_desc=json.dumps(json_schema, ensure_ascii=False, indent=2),
        flow_types=flow_types,
        criteria_names=criteria_names
    )