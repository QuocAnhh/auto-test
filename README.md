# Bus QA LLM Evaluator (Modular)

Project đa file để chấm điểm hội thoại nhà xe bằng LLM.

## Tính năng
- Nhập `conversation_id` → gọi API `GET /api/conversations/<id>/messages` từ `BASE_URL`
- Chuẩn hoá transcript, tính metrics (latency, số lượt trao đổi...)
- Gọi LLM (OpenAI-compatible) với prompt **rõ ràng + JSON Schema** để chấm điểm theo **rubrics nghiệp vụ**:
  - Đặt vé / Đổi vé / Hủy vé / Đổi chỗ / Hỏi thông tin
- Kết quả: điểm từng tiêu chí (0–100), điểm tổng (weighted), nhãn xếp hạng, rủi ro, gợi ý cải thiện
- UI Streamlit, có nút tải JSON kết quả

## Cách chạy nhanh
```bash
pip install -r requirements.txt
streamlit run app.py
```

- Nhập `BASE_URL` (mặc định: `http://103.141.140.243:14496`)
- Nhập `conversation_id`
- (Tuỳ chọn) Headers JSON nếu API cần xác thực
- Nhập `LLM API Key`, `Model` (ví dụ `gpt-4o-mini`), và (tuỳ chọn) `LLM Base URL` nếu bạn dùng cổng nội bộ.

## Cấu trúc
```
bus_qa_llm_project/
├─ app.py                 # UI Streamlit
├─ requirements.txt
├─ README.md
├─ busqa/
│  ├─ __init__.py
│  ├─ models.py          # Pydantic models
│  ├─ api_client.py      # Gọi API hội thoại
│  ├─ normalize.py       # Chuẩn hoá transcript
│  ├─ metrics.py         # Tính latency/turns
│  ├─ rubrics.py         # Bộ tiêu chí (weights)
│  ├─ prompting.py       # System/User prompts + JSON Schema
│  ├─ llm_client.py      # OpenAI-compatible client + retries
│  ├─ evaluator.py       # Hợp nhất: build prompt → gọi LLM → validate → fill missing keys
│  └─ utils.py           # Tiện ích
└─ tests/
   └─ smoke_test.py
```

## Ghi chú về Prompting
- **System prompt** quy định rõ intent hợp lệ, nguyên tắc chấm, thang điểm, cách dùng metrics, cách phạt nếu thiếu dữ kiện.
- **User instruction** chèn **JSON Schema** cụ thể: bắt buộc `criteria` phải chứa ĐẦY ĐỦ các tiêu chí của rubric theo intent đã chọn.
- **LLM** được yêu cầu `response_format={"type":"json_object"}` để chắc chắn trả JSON.
- Trên app có validate + điền mặc định 0 điểm cho tiêu chí thiếu, rồi tính lại weighted total, đảm bảo tính nhất quán.

## Mở rộng
- Xuất .xlsx tổng hợp nhiều conversation_id
- Rule-based fallback khi LLM lỗi
- Thêm dashboard tổng hợp team/agent theo tuần