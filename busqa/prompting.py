import json
from .rubrics import ALLOWED_INTENTS, RUBRICS

SYSTEM_PROMPT = f"""
Bạn là QA Lead của một nhà xe. Đọc transcript hội thoại giữa KH (USER) và CSKH (AGENT),
xác định intent chính (chỉ chọn 1 trong: {', '.join(ALLOWED_INTENTS)}),
rồi chấm điểm theo đúng bộ tiêu chí của intent đó. Chấm nghiêm túc, thang 0–100.
50 = đạt tối thiểu; 80 = tốt; 90+ = xuất sắc; 100 chỉ khi không có điểm trừ đáng kể.

Nguyên tắc:
- Chấm năng lực của AGENT, KHÔNG chấm hành vi khách hàng.
- Ưu tiên tuân thủ quy trình: xác thực/điều kiện, kiểm tra hệ thống, chính sách, bằng chứng (PNR, biên nhận).
- Sử dụng metrics (latency) để đánh giá “Tốc độ phản hồi” nếu có trong rubric.
- Nếu transcript thiếu dữ kiện quan trọng, trừ điểm tương xứng và ghi rõ ở note.
- Trả về **JSON THUẦN** (không kèm văn bản khác).
- Nếu có tình huống rủi ro (sai chính sách, cam kết quá mức, tiềm ẩn khiếu nại) thì thêm vào 'risks' & 'tags'.
- Ngôn ngữ: tiếng Việt, súc tích, cụ thể.

Intent & Rubrics (tiêu chí + trọng số):
{{rubrics_json}}
"""

JSON_SCHEMA = {
    "type": "object",
    "required": ["version", "detected_intent", "confidence", "criteria", "total_score", "label", "final_comment"],
    "properties": {
        "version": {"type": "string"},
        "detected_intent": {"type": "string", "enum": ALLOWED_INTENTS},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "criteria": {"type": "object"},
        "total_score": {"type": "number", "minimum": 0, "maximum": 100},
        "label": {"type": "string", "enum": ["Xuất sắc","Tốt","Đạt","Cần cải thiện","Kém"]},
        "final_comment": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}}
    },
    "additionalProperties": True
}

USER_INSTRUCTION_TEMPLATE = """
DỮ LIỆU ĐẦU VÀO
---------------
[Metrics]
{metrics_json}

[Transcript - dạng dòng]
{transcript}

YÊU CẦU ĐẦU RA (JSON)
----------------------
Tuân thủ JSON Schema sau (mô tả, KHÔNG cần trả lại schema):
{json_schema}

QUY TẮC BẮT BUỘC:
- Chọn đúng 1 intent trong {allowed_intents}.
- Với intent đã chọn, 'criteria' PHẢI bao gồm TẤT CẢ các tiêu chí (đúng tên) trong rubric tương ứng.
- Mỗi tiêu chí dạng: {{"score": 0..100, "note": "giải thích ngắn, cụ thể"}}.
- 'total_score' = sum(score_i * weight_i) theo rubric (đã có trong system message).
- 'label' theo ngưỡng: >=90 Xuất sắc; 80-89 Tốt; 65-79 Đạt; 50-64 Cần cải thiện; <50 Kém.
- Nên thêm 'tags' (root-cause), 'risks' (nếu có), 'suggestions' (2-4 đề xuất cụ thể).
"""

def build_user_prompt(metrics: dict, transcript: str) -> str:
    rubrics_json = json.dumps(RUBRICS, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}");
    json_schema = json.dumps(JSON_SCHEMA, ensure_ascii=False, indent=2).replace("{", "{{").replace("}", "}}");
    return USER_INSTRUCTION_TEMPLATE.format(
        metrics_json=json.dumps(metrics, ensure_ascii=False, indent=2),
        transcript=transcript,
        json_schema=json_schema,
        allowed_intents=ALLOWED_INTENTS,
        rubrics_json=rubrics_json
    )