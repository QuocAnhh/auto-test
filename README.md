# Bus QA LLM Project

Hệ thống đánh giá chất lượng hội thoại chatbot/tổng đài tự động sử dụng LLM (Large Language Model) cho ngành vận tải hành khách.

## Tổng quan

Dự án này cung cấp một hệ thống hoàn chỉnh để:
- Lấy dữ liệu hội thoại từ API
- Phân tích và đánh giá chất lượng hội thoại theo 8 tiêu chí thống nhất
- Phát hiện vi phạm chính sách và vấn đề vận hành
- Tạo báo cáo chi tiết với insights và metrics

## Kiến trúc hệ thống

### Luồng hoạt động chính:

1. **Thu thập dữ liệu**:
   - API call tới `GET /api/conversations?bot_id=xxx&page=x&page_size=xx` để lấy danh sách conversations kèm messages
   - Normalize messages thành format chuẩn với sender_type, timestamp, text

2. **Phân tích metrics**:
   - Tính toán latency (first response, average response time)
   - Phát hiện các vấn đề: repeated questions, context resets, policy violations
   - Diagnostic hits theo operational_readiness và risk_compliance

3. **Đánh giá LLM**:
   - Build system prompt từ rubrics + brand policy + brand prompt
   - Build user prompt từ transcript + metrics
   - Call LLM (OpenAI/Gemini) với JSON response format
   - Coerce kết quả thành 8 tiêu chí chuẩn

4. **Xử lý kết quả**:
   - Apply penalties dựa trên policy violations và diagnostic hits
   - Tính toán weighted score từ 8 criteria
   - Generate insights và summary statistics

### API Endpoint chính:

- `GET /api/conversations?bot_id={bot_id}&page={page}&page_size={page_size}` - Lấy danh sách conversations kèm toàn bộ messages

### 8 Tiêu chí đánh giá thống nhất:

1. **intent_routing** (15%) - Định tuyến ý định đúng
2. **slots_completeness** (25%) - Thu thập đầy đủ thông tin
3. **no_redundant_questions** (15%) - Không hỏi lại thông tin đã có
4. **knowledge_accuracy** (15%) - Độ chính xác thông tin
5. **context_flow_closure** (15%) - Kết thúc hội thoại phù hợp
6. **style_tts** (10%) - Phong cách phù hợp TTS
7. **policy_compliance** (3%) - Tuân thủ chính sách
8. **empathy_experience** (2%) - Thể hiện empathy

## Cài đặt và chạy

### Yêu cầu hệ thống:
- Python 3.12+
- OpenAI API key hoặc Gemini API key
- Bearer token để access conversation API

### Cài đặt:
```bash
pip install -r requirements.txt
```

### Cấu hình môi trường:
```bash
# .env file
OPENAI_API_KEY=your_openai_key
# hoặc
GEMINI_API_KEY=your_gemini_key
BEARER_TOKEN=your_bearer_token
```

### Chạy ứng dụng:

1. **Streamlit Web App** (khuyến nghị):
```bash
streamlit run app.py
```

2. **CLI đánh giá đơn lẻ**:
```bash
python evaluate_cli.py --conversation-id conv_123 --brand-prompt-path brands/son_hai/prompt.md
```

3. **CLI đánh giá batch**:
```bash
python evaluate_cli.py --conversation-ids "conv1,conv2,conv3" --brand-mode auto-by-botid
```

4. **Bulk List & Evaluate**:
```bash
python tools/bulk_list_evaluate.py --bot-id 3794 --brand son_hai --take 20
```

5. **Docker**:
```bash
docker-compose up
```

## Cấu trúc thư mục

```
├── app.py                 # Streamlit web interface chính
├── evaluate_cli.py        # CLI evaluation tool
├── busqa/                 # Core evaluation modules
│   ├── api_client.py      # API calls
│   ├── normalize.py       # Message normalization
│   ├── metrics.py         # Metrics computation
│   ├── evaluator.py       # LLM evaluation logic
│   ├── brand_resolver.py  # Multi-brand support
│   └── ...
├── config/
│   ├── rubrics_unified.yaml    # 8 tiêu chí + weights
│   ├── diagnostics.yaml        # Diagnostic rules
│   └── bot_map.yaml            # Bot ID -> Brand mapping
├── brands/
│   ├── son_hai/prompt.md       # Brand-specific prompts
│   └── long_van/prompt.md
├── tools/
│   └── bulk_list_evaluate.py   # Bulk fetching + evaluation
└── tests/                      # Unit tests
```

## Tính năng chính

### Multi-brand Support:
- `single`: Dùng 1 brand cho tất cả conversations
- `auto-by-botid`: Tự động resolve brand dựa trên bot_id từ conversation

### Batch Processing:
- Hỗ trợ đánh giá up to 50 conversations song song
- Concurrent LLM calls với rate limiting
- Progress tracking và error handling

### Diagnostic System:
- Phát hiện vi phạm operational readiness
- Risk compliance checking
- Automatic penalty application

### Export Options:
- JSON reports với full details
- CSV summary
- PDF reports với charts
- HTML reports

## Next Steps - Đề xuất phát triển

### 1. Cải thiện hiệu suất & Reliability
- **Database integration**: PostgreSQL để lưu evaluation history, caching results
- **Rate limiting tối ưu**: Hiện tại có retry/backoff, cần fine-tune cho production
- **Connection pooling**: Tối ưu API calls với connection reuse
- **Error recovery**: Improve error handling cho LLM timeouts và API failures

### 2. Mở rộng Data Processing
- **Streaming evaluation**: Real-time evaluation khi có conversation mới
- **Batch scheduling**: Cron jobs để chạy evaluation định kỳ theo schedule
- **Data warehouse integration**: Export results tới BigQuery/Snowflake cho analytics
- **Historical trend analysis**: Track quality metrics qua thời gian

### 3. Multi-brand Management nâng cao
- **Brand-specific rubrics**: Cho phép mỗi brand có rubrics khác nhau
- **Dynamic brand resolution**: Auto-detect brand từ conversation content
- **Brand performance comparison**: Dashboard so sánh quality giữa các brands
- **Custom diagnostic rules**: Brand-specific policy violation detection

### 4. LLM & AI Improvements
- **Model comparison**: A/B test giữa OpenAI vs Gemini vs local models
- **Custom fine-tuning**: Fine-tune model cho domain transportation
- **Confidence scoring**: Thêm confidence score cho LLM evaluations
- **Automated prompt optimization**: Test different prompts và chọn best performer

### 5. API & Integration
- **REST API**: Expose evaluation capabilities qua HTTP endpoints
- **Webhook support**: Push notifications khi có quality alerts
- **Slack/Teams integration**: Notifications cho critical quality issues
- **Third-party connectors**: Integration với CRM, ticketing systems

### 6. Advanced Analytics & Monitoring
- **Real-time dashboard**: Live quality metrics với alerts
- **Anomaly detection**: Phát hiện conversations bất thường
- **Root cause analysis**: Tự động identify patterns gây quality issues
- **Performance benchmarking**: So sánh với industry standards

### 7. Operational Excellence
- **Multi-environment support**: Dev/staging/prod configs
- **Audit logging**: Track all evaluations và config changes
- **Role-based access control**: Phân quyền user access
- **Backup & disaster recovery**: Data protection strategies

### 8. UI/UX Enhancements
- **Mobile-responsive**: Tối ưu Streamlit app cho mobile
- **Advanced filtering**: Filter results theo multiple criteria
- **Export improvements**: PDF reports với charts và insights
- **Custom dashboards**: Configurable dashboards cho từng team

**Ưu tiên cao nhất**: Database integration, API endpoints, và real-time monitoring sẽ tạo foundation mạnh cho scaling system này thành enterprise-grade platform.
