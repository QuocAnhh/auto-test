# Bus QA LLM Evaluator - Unified Rubric System v1.0

**Chỉ sử dụng một bộ tiêu chí chung** (8 tiêu chí cố định) cho mọi nhà xe. Brand chỉ là tri thức & policy.

## Tính năng chính
- **Unified Rubric**: 8 tiêu chí cố định cho tất cả nhà xe
- **Brand as Knowledge**: Mỗi brand chỉ cung cấp tri thức, flow và policy (không định nghĩa tiêu chí riêng)
- **Rule-based Metrics**: Phát hiện tự động các vấn đề (không dựa vào latency nếu null)
- **Policy Enforcement**: Tự động áp dụng penalty khi vi phạm policy
- **Streamlit UI + CLI**: Giao diện web và command line

## 8 Tiêu chí chung (Unified Rubric v1.0)
1. **intent_routing** (15%): Hiểu đúng ý định khách và định tuyến vào flow phù hợp
2. **slots_completeness** (25%): Thu thập đầy đủ thông tin cần thiết theo flow  
3. **no_redundant_questions** (15%): Không hỏi lại thông tin đã có hoặc không cần thiết
4. **knowledge_accuracy** (15%): Cung cấp thông tin chính xác về lịch trình, giá vé, chính sách
5. **context_flow_closure** (15%): Duy trì ngữ cảnh và kết thúc cuộc gọi hợp lý
6. **style_tts** (10%): Phong cách giao tiếp và đọc số liệu phù hợp
7. **policy_compliance** (3%): Tuân thủ chính sách công ty và quy định
8. **empathy_experience** (2%): Thể hiện sự đồng cảm và tạo trải nghiệm tích cực

## Hệ thống Diagnostics (Chẩn đoán Vệ tinh)

Hệ thống diagnostics tự động phát hiện các lỗi nghiệp vụ và tuân thủ, sau đó áp dụng "điểm trừ thông minh" vào 8 tiêu chí hiện có.

### 2 Nhóm Diagnostics

**Operational Readiness (Sẵn sàng Nghiệp vụ):**
- `double_room_rule_violation`: Chào bán phòng đôi sai vị trí quy định
- `child_policy_miss`: Không áp dụng chính sách trẻ em khi có trẻ <10 tuổi
- `pickup_scope_violation`: Xác minh tuyến khi policy cấm
- `fare_math_inconsistent`: Nêu giá vé mâu thuẫn (chênh >20%)
- `handover_sla_missing`: Kết thúc thiếu cam kết SLA

**Risk Compliance (Tuân thủ Rủi ro):**
- `forbidden_phone_collect`: Thu thập SĐT khi policy cấm
- `promise_hold_seat`: Hứa giữ chỗ trái thẩm quyền
- `payment_policy_violation`: Tư vấn thanh toán trái chính sách
- `pdpa_consent_missing`: Thu thập dữ liệu thiếu consent

### Cách hoạt động

1. **Rule-based Detection**: Phát hiện tự động bằng heuristic (ưu tiên tránh False Positive)
2. **Smart Penalties**: Ánh xạ điểm trừ vào tiêu chí liên quan:
   - `delta`: Cộng/trừ điểm trực tiếp
   - `clamp_max`: Giới hạn điểm tối đa
3. **Evidence-based**: Mỗi hit có bằng chứng (trích dẫn turn cụ thể)
4. **Configurable**: Dễ mở rộng qua `config/diagnostics.yaml`

### Bật/Tắt Diagnostics

**UI**: Checkbox "Apply diagnostic penalties" trong sidebar
**CLI**: Flag `--apply-diagnostics` / `--no-diagnostics`

Khi tắt: Vẫn hiển thị hit nhưng không áp phạt điểm.

## Cách chạy

### Streamlit UI
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_api_key_here
streamlit run app.py
```

1. Chọn brand (son_hai hoặc phuong_trang)
2. Nhập `conversation_id`
3. Nhấn "Chấm điểm" → tự động sử dụng Unified Rubric System

### CLI
```bash
python evaluate_cli.py \
  --conversation-id "conv_123" \
  --brand-prompt-path "brands/son_hai/prompt.md" \
  --output "result.json" \
  --verbose
```

## Cấu trúc Project
```
bus_qa_llm_project/
├─ app.py                      # Streamlit UI với Unified Rubric
├─ evaluate_cli.py            # CLI evaluation tool
├─ config/
│  └─ rubrics_unified.yaml    # ⭐ Unified Rubric config (8 tiêu chí chung)
├─ brands/                    # ⭐ Brand prompts (tri thức + policy)
│  ├─ son_hai/prompt.md      
│  └─ phuong_trang/prompt.md
├─ busqa/
│  ├─ prompt_loader.py       # ⭐ Load unified rubrics
│  ├─ brand_specs.py         # ⭐ Brand policy dataclass
│  ├─ prompting.py           # ⭐ Unified system/user prompts
│  ├─ evaluator.py           # ⭐ Unified coercion + penalties
│  ├─ metrics.py             # Rule-based metrics (no latency if null)
│  └─ (other modules...)
└─ tests/
   └─ test_unified_rubric.py  # Unified system tests
```

## Cách thêm Brand mới

1. Tạo thư mục `brands/<brand_name>/`
2. Tạo file `prompt.md` với front-matter:

```yaml
---
brand_id: "new_brand"
policies:
  forbid_phone_collect: true    # Cấm thu thập SĐT
  require_fixed_greeting: false # Bắt buộc chào cố định
  ban_full_summary: true        # Cấm tóm tắt toàn bộ
  max_prompted_openers: 1       # Giới hạn gợi ý mở đầu
tts:
  read_money_in_words: true     # Bắt buộc đọc tiền bằng chữ
---

# Brand Knowledge & Flow Content
(Tri thức về tuyến xe, giá vé, chính sách, flow giao tiếp...)
```

3. Brand **KHÔNG định nghĩa** tiêu chí mới - chỉ ảnh hưởng điểm `knowledge_accuracy`, `policy_compliance`, `context_flow_closure`

## Unified System Logic

- **Rubric**: 8 tiêu chí cố định từ `config/rubrics_unified.yaml`
- **Brand**: Chỉ cung cấp tri thức + policy flags
- **Metrics**: Rule-based detection (redundant questions, policy violations, etc.)
- **Penalties**: Tự động áp dụng khi phát hiện vi phạm
- **Output**: Luôn có đủ 8 tiêu chí, điểm tổng theo unified weights

## Acceptance Test

Cùng 1 transcript nhưng chạy với 2 brand khác nhau:
- ✅ **Bộ tiêu chí giống hệt nhau** (8 tiêu chí)
- ✅ Chỉ điểm `knowledge_accuracy`/`policy_compliance` khác nhau
- ✅ Điểm tổng tính theo cùng 1 formula