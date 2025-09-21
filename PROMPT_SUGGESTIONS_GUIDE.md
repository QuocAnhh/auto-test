# 🎯 Hướng Dẫn Sử Dụng Chức Năng Prompt Suggestions

## 📋 Tổng Quan

Chức năng **Prompt Suggestions** cho phép phân tích kết quả đánh giá và đưa ra gợi ý cải thiện prompt của brand một cách thông minh, dựa trên LLM.

## 🚀 Cách Sử Dụng

### 1. Chạy Ứng Dụng

```bash
# Chạy Docker container
cd /home/quocanh/Downloads/bus_qa_llm_project
docker compose up
```

Ứng dụng sẽ chạy tại: `http://localhost:8000`

### 2. Sử Dụng Frontend

1. **Mở trình duyệt** và truy cập `http://localhost:8000`
2. **Chọn brand** từ dropdown
3. **Chạy đánh giá** với một số conversations
4. **Chuyển sang tab "Prompt Suggestions"**
5. **Click "Analyze Prompt"** để phân tích

### 3. Sử Dụng API Trực Tiếp

```bash
curl -X POST "http://localhost:8000/analyze/prompt-suggestions" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_id": "long_van",
    "evaluation_summary": {
      "count": 10,
      "successful_count": 10,
      "avg_total_score": 68.5,
      "criteria_avg": {
        "empathy_experience": 60,
        "slots_completeness": 75,
        "knowledge_accuracy": 70
      }
    }
  }'
```

## 🔧 Các Tính Năng Chính

### 1. Phân Tích Thông Minh
- **Phân tích patterns** từ evaluation summary
- **Xác định vấn đề** cụ thể trong prompt
- **Đưa ra gợi ý** cải thiện chính xác

### 2. Gợi Ý Cụ Thể
- **Chỉ ra chính xác** phần nào của prompt cần sửa
- **Cung cấp code mới** để thay thế
- **Giải thích lý do** tại sao cần sửa
- **Ước tính cải thiện** điểm số

### 3. Giao Diện Trực Quan
- **Hiển thị diff** trước/sau
- **Phân loại theo độ ưu tiên** (high/medium/low)
- **Tương tác dễ dàng** với các gợi ý

## 📊 Ví Dụ Kết Quả

```json
{
  "criterion": "empathy_experience",
  "avg_score": 60,
  "target_score": 85,
  "problem_pattern": "Empathy experience thấp (60/100) - thiếu sự đồng cảm và trải nghiệm tích cực",
  "prompt_section": "conversation_style",
  "line_range": [1, 3],
  "current_code": "## PHONG CÁCH GIAO TIẾP\n- Lịch sự, chuyên nghiệp\n- Trả lời ngắn gọn",
  "suggested_code": "## PHONG CÁCH GIAO TIẾP\n- Lịch sự, chuyên nghiệp, thân thiện\n- Thể hiện sự đồng cảm với khách hàng\n- Sử dụng ngôn ngữ tích cực và hỗ trợ\n- Hỏi thêm về nhu cầu và mong muốn của khách\n- Đưa ra lời khuyên hữu ích",
  "reasoning": "Dựa trên evaluation summary: empathy_experience chỉ đạt 60/100. Cần cải thiện phong cách giao tiếp để tạo trải nghiệm tích cực hơn cho khách hàng.",
  "priority": "medium",
  "expected_improvement": "+25 điểm empathy_experience"
}
```

## 🧪 Test Chức Năng

### Test Backend
```bash
python3 test_prompt_suggestions.py
```

### Test Frontend Integration
```bash
python3 test_frontend_integration.py
```

## 📁 Cấu Trúc Files

```
bus_qa_llm_project/
├── busqa/
│   ├── prompt_doctor.py          # Core LLM analysis logic
│   └── aggregate.py              # Evaluation summary generation
├── frontend/
│   ├── index.html                # Main UI with Prompt Suggestions tab
│   └── assets/js/
│       ├── main.js               # Frontend integration
│       └── components/
│           └── prompt-suggestions.js  # UI component
├── api.py                        # API endpoints
└── test_prompt_suggestions.py    # Test script
```

## 🎯 Các Tiêu Chí Được Hỗ Trợ

1. **intent_routing** - Định tuyến ý định
2. **slots_completeness** - Đầy đủ thông tin
3. **no_redundant_questions** - Không hỏi thừa
4. **knowledge_accuracy** - Chính xác kiến thức
5. **context_flow_closure** - Đóng context flow
6. **style_tts** - Phong cách TTS
7. **policy_compliance** - Tuân thủ policy
8. **empathy_experience** - Trải nghiệm đồng cảm

## 🔄 Workflow

1. **Chạy đánh giá** conversations
2. **Tạo evaluation summary** từ kết quả
3. **Phân tích prompt** dựa trên summary
4. **Xem gợi ý** cải thiện cụ thể
5. **Áp dụng** các gợi ý vào prompt
6. **Test lại** để xem cải thiện

## 🚨 Lưu Ý

- Cần có **evaluation results** trước khi phân tích
- **Brand prompt** phải tồn tại trong thư mục `brands/`
- **API server** phải chạy để sử dụng frontend
- **Docker container** đã được tích hợp sẵn chức năng

## 🎉 Kết Luận

Chức năng Prompt Suggestions giúp:
- **Tự động phát hiện** vấn đề trong prompt
- **Đưa ra gợi ý** cải thiện cụ thể
- **Tăng hiệu quả** đánh giá và cải thiện
- **Tiết kiệm thời gian** cho việc tối ưu prompt

Hãy thử nghiệm và cho feedback để cải thiện thêm! 🚀