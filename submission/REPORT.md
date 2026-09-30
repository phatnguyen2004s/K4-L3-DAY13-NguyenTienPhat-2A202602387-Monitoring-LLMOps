# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:**
- **MSSV:**
- **Lớp:** K4-L3B
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602387`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (`evidence/00-baseline-log-validator.txt`) | 100/100 sau CP1 (`evidence/02-log-validator.txt`) | Baseline thiếu field bắt buộc, correlation ID = `MISSING`, chưa enrich context |
| `validate_dashboard.py` | 6/6 panel (`evidence/00-baseline-dashboard-validator.txt`) | | Contract có sẵn; chưa có dashboard runtime |
| `pytest` | 22 passed (`evidence/00-baseline-pytest.txt`) | 30 passed sau CP1 (`evidence/01-pytest-cp1.txt`) | Thêm 8 test cho PII, correlation ID và enrichment |
| Số traces hợp lệ | 0 | | Chưa cấu hình key Langfuse (`tracing_enabled: false`) |
| Số PII leak | 0 | 0 (`evidence/05-pii-redaction.txt`) | Baseline chỉ có 0 vì preview đã qua `summarize_text()`; CP1 thêm processor scrub toàn bộ event |
| Latency P95 / TTFT P95 | 160 ms / 55 ms | | 10 request, `load_test.py` concurrency 1 (`evidence/00-baseline-metrics.txt`) |
| Retrieval success rate | 100% (10/10) | | Không bật incident |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` gọi `clear_contextvars()` ở đầu mỗi request để không rò context từ request trước. Nếu header `x-request-id` đúng format `req-<8-hex>` thì dùng lại (chuẩn hóa về chữ thường); nếu thiếu hoặc sai format (ví dụ chứa email) thì sinh ID mới `req-{uuid4().hex[:8]}` thay vì ghi nguyên văn. ID được bind vào structlog contextvars, gắn vào `request.state` và được `LabAgent` đưa vào trace metadata. Response trả lại qua header `x-request-id`, `x-response-time-ms` và body `correlation_id`.
- **Các metadata được ghi vào structured log:** mọi record của `service=api` có `ts`, `level`, `event`, `correlation_id`, cùng context bind trong `/chat`: `user_id_hash` (SHA-256 cắt 12 ký tự, không log `user_id` gốc), `session_id`, `feature`, `model`, `env`. `response_sent` thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` được đăng ký sau `format_exc_info`, để stack trace cũng được scrub, và trước `JsonlFileProcessor`/`JSONRenderer`. Processor scrub đệ quy mọi chuỗi trong event (kể cả dict/list lồng trong `payload`), chỉ bỏ qua field hệ thống `ts`, `level`, `correlation_id`, `user_id_hash`. `app/pii.py` có pattern cho email, thẻ, CCCD, điện thoại VN, hộ chiếu VN và địa chỉ theo từ khóa (số nhà/ngõ/đường/phường/quận…). Pattern thẻ và CCCD chạy trước điện thoại để chuỗi số dài không bị redact nhầm loại. Đánh đổi: địa chỉ không có dấu phẩy có thể bị redact dư tối đa 4 từ, chấp nhận được vì an toàn quan trọng hơn trong log.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100 (10 correlation ID khác nhau, 0 record thiếu field/enrichment, 0 PII leak). Test `tests/test_correlation_logging.py` kiểm tra format ID, dùng lại/thay thế header, enrichment không rò giữa hai request liên tiếp và PII không xuất hiện trong file log. Gửi 4 request chứa PII mẫu rồi `grep` nguyên văn cho kết quả 0 dòng (`evidence/05-pii-redaction.txt`). File log ghi UTF-8 (`ensure_ascii=False`) để `grep` tiếng Việt có ý nghĩa. Cả 10/10 correlation ID của lượt load test đều tìm được trace có cùng `correlation_id` trong metadata trên Langfuse.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:**
- **Cách nối trace với log:**
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
- **SLO và lý do chọn:**
- **Cách tính error budget:**
- **Ba alert và runbook tương ứng:**

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:** (CP0) Sau khi điền key, `/health` báo `tracing_enabled: true` nhưng project Langfuse không có trace nào. Log API có `Failed to export spans batch ... SSLError(CERTIFICATE_VERIFY_FAILED)`, sau đó là `Read timed out`.
- **Cách tìm nguyên nhân và xử lý:** `auth_check()` qua `httpx` thành công, vì `httpx` dùng bundle `certifi`, nên key không sai. OTLP exporter lại dùng `urllib3` với SSL context mặc định, mà Python 3.13 cài từ python.org trên macOS không có `etc/openssl/cert.pem`. `urllib.request` lỗi khi chưa đặt `SSL_CERT_FILE` và trả 200 khi trỏ biến này tới `certifi.where()`. Vì vậy tôi thêm `SSL_CERT_FILE` vào `.env`. Mạng tới `cloud.langfuse.com` chậm (connect 2–3 s), còn timeout mặc định của SDK là 5 s, nên tôi đặt thêm `LANGFUSE_TIMEOUT=30`. Kết quả: lượt load test sau đó export đủ 10/10 trace. Tôi cũng ghi nhận API `GET /api/public/traces` trả 410 cho org mới, nên dùng `GET /api/public/v2/observations` để đếm trace.
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
