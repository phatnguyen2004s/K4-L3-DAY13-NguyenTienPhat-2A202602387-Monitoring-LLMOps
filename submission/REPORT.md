# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:**
- **MSSV:**
- **Lớp:** K4-L3B
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602387`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 (`evidence/00-baseline-log-validator.txt`) | 100/100 sau CP1 (`evidence/02-log-validator.txt`) | Baseline thiếu field bắt buộc, correlation ID = `MISSING`, chưa enrich context |
| `validate_dashboard.py` | 6/6 panel (`evidence/00-baseline-dashboard-validator.txt`) | 6/6 panel + dashboard runtime (`evidence/03-dashboard-validator.txt`, `evidence/11-*.jpg`) | Dashboard `scripts/dashboard.py` đọc `data/logs.jsonl` theo đúng contract |
| `pytest` | 22 passed (`evidence/00-baseline-pytest.txt`) | 30 passed sau CP1 (`evidence/01-pytest-cp1.txt`) | Thêm 8 test cho PII, correlation ID và enrichment |
| Số traces hợp lệ | 0 | 47 trace có `correlation_id=req-…` trong 90 phút (`evidence/06-trace-list.txt`) | Mỗi trace: root `lab-agent-run` + `retrieval`, `prompt-resolve`, `llm-generation` |
| Số PII leak | 0 | 0 (`evidence/05-pii-redaction.txt`) | Baseline chỉ có 0 vì preview đã qua `summarize_text()`; CP1 thêm processor scrub toàn bộ event |
| Latency P95 / TTFT P95 | 160 ms / 55 ms | steady-state ≈ 170–440 ms / 60 ms; request lạnh ≈ 1.05 s | Baseline chưa có key; sau khi bật Langfuse, request đầu phải fetch prompt (0.89 s, thấy rõ ở span `prompt-resolve`) |
| Retrieval success rate | 100% (10/10) | 100% khi không có incident; 79.6% trong practice `tool_fail` | Panel errors chuyển BREACH đúng như kỳ vọng |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` gọi `clear_contextvars()` ở đầu mỗi request để không rò context từ request trước. Nếu header `x-request-id` đúng format `req-<8-hex>` thì dùng lại (chuẩn hóa về chữ thường); nếu thiếu hoặc sai format (ví dụ chứa email) thì sinh ID mới `req-{uuid4().hex[:8]}` thay vì ghi nguyên văn. ID được bind vào structlog contextvars, gắn vào `request.state` và được `LabAgent` đưa vào trace metadata. Response trả lại qua header `x-request-id`, `x-response-time-ms` và body `correlation_id`.
- **Các metadata được ghi vào structured log:** mọi record của `service=api` có `ts`, `level`, `event`, `correlation_id`, cùng context bind trong `/chat`: `user_id_hash` (SHA-256 cắt 12 ký tự, không log `user_id` gốc), `session_id`, `feature`, `model`, `env`. `response_sent` thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` được đăng ký sau `format_exc_info`, để stack trace cũng được scrub, và trước `JsonlFileProcessor`/`JSONRenderer`. Processor scrub đệ quy mọi chuỗi trong event (kể cả dict/list lồng trong `payload`), chỉ bỏ qua field hệ thống `ts`, `level`, `correlation_id`, `user_id_hash`. `app/pii.py` có pattern cho email, thẻ, CCCD, điện thoại VN, hộ chiếu VN và địa chỉ theo từ khóa (số nhà/ngõ/đường/phường/quận…). Pattern thẻ và CCCD chạy trước điện thoại để chuỗi số dài không bị redact nhầm loại. Đánh đổi: địa chỉ không có dấu phẩy có thể bị redact dư tối đa 4 từ, chấp nhận được vì an toàn quan trọng hơn trong log.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100 (10 correlation ID khác nhau, 0 record thiếu field/enrichment, 0 PII leak). Test `tests/test_correlation_logging.py` kiểm tra format ID, dùng lại/thay thế header, enrichment không rò giữa hai request liên tiếp và PII không xuất hiện trong file log. Gửi 4 request chứa PII mẫu rồi `grep` nguyên văn cho kết quả 0 dòng (`evidence/05-pii-redaction.txt`). File log ghi UTF-8 (`ensure_ascii=False`) để `grep` tiếng Việt có ý nghĩa. Cả 10/10 correlation ID của lượt load test đều tìm được trace có cùng `correlation_id` trong metadata trên Langfuse.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** `auth_check()` với key trong `.env` trả về đúng một project `day13-k4-l3b-2A202602387`; ảnh Langfuse có tên project trên breadcrumb. Mỗi trace mang `correlation_id` do middleware của tôi sinh (ví dụ `req-b1000002`), tìm lại được trong `data/logs.jsonl` bằng `python scripts/log_query.py --id <id>`.
- **Cấu trúc root/retrieval/generation observations:** trace `day13-agent-request` → root `lab-agent-run` (agent) → `retrieval` (retriever: preview query đã scrub, `doc_count`), `prompt-resolve` (span: name/label/version/source/fetch_error, `WARNING` nếu fallback), `llm-generation` (generation: `model`, `usage_details` input/output, `cost_details` input/output/total, `completion_start_time` = TTFT, `prompt` link tới version Langfuse). Mọi child dùng `@observe(capture_input=False, capture_output=False)`, chỉ ghi preview đã qua `summarize_text()`. Tôi thêm `prompt-resolve` vì waterfall ban đầu có khoảng trống 0.9 s giữa retrieval và generation không giải thích được (`evidence/07-trace-waterfall.*`).
- **Cách nối trace với log:** `correlation_id` được đưa vào `propagate_attributes(metadata=...)` nên xuất hiện trên mọi observation của trace, trùng với field `correlation_id` trong log và header `x-request-id`. Tra cứu: `python scripts/log_query.py --id <id>` → `python scripts/trace_lookup.py <id>` (`evidence/08-trace-metadata.txt`). 10/10 correlation ID của một lượt load test đều tìm được trace.
- **Prompt name:** `day13-chat` (text prompt, 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`), quản lý bằng `scripts/prompt_admin.py`.
- **Version/label baseline:** v1, labels `baseline` + `production`, template gốc của lab (cùng input → `tokens_in=32`).
- **Version/label candidate:** v2, label `candidate`, thêm dòng "Answer in at most 3 short bullet points and cite the doc you used." (cùng input → `tokens_in=49`).
- **Trace ID của mỗi version:** baseline/v1 `dcea7af45dec931091567d2d7b173333` (`req-b1000002`); candidate/v2 `565c6c30c517c9a9cf03c6e9e946920b` (`req-c2000002`); production sau promote → v2 `dca36b441c2978a41122dc4431cf3e2b` (`req-a2000012`); production sau rollback → v1 `92dd2f5eda0fcd94aa0cd0263fdd07d1` (`req-a1000022`).
- **Cách promote và rollback `production`:** `python scripts/prompt_admin.py promote --version 2` rồi `--version 1` (gọi `update_prompt(new_labels=["production", ...])`; label là duy nhất nên gắn cho version này sẽ gỡ khỏi version kia). API chạy liên tục, không sửa code/không restart. SDK cache prompt 60s kiểu stale-while-revalidate: request đầu sau TTL vẫn nhận bản cũ và kích hoạt refresh nền, request kế tiếp mới dùng version mới ⇒ thời gian rollback có hiệu lực ≈ 60s + 1 request (`evidence/10-prompt-rollback.txt`).

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `python scripts/dashboard.py` (process tách khỏi API, http://127.0.0.1:8050) đọc `data/logs.jsonl`; `app/dashboard_data.py` lấy title/unit/threshold từ `config/dashboard.yaml` nên luôn khớp contract. Time range 60 phút, auto refresh 30s, mỗi panel có đơn vị, đường threshold nét đứt và badge OK/BREACH: latency P50/P95/P99 + TTFT P95; traffic count + req/phút; error rate + breakdown `error_type` + retrieval success; cost cộng dồn + theo phút; tokens in/out; quality mean. Practice `tool_fail`: panel errors chuyển BREACH (error rate 20.41%, retrieval success 79.6%, `RuntimeError: 10`) trong khi các panel khác giữ nguyên (`evidence/11-dashboard-practice-tool-fail.jpg`).
- **SLO và lý do chọn:** giữ `fast_successful_requests`: 99.5% request thành công **và** `latency_ms ≤ 3000` trong 28 ngày. Baseline của tôi: steady-state P95 ≈ 170–440 ms, request lạnh fetch prompt ≈ 1.05 s, nên 3000 ms dư ~2.7× cho request lạnh nhưng vẫn bắt được sự cố thật (prompt fetch fallback 3–4 s ở CP1, retrieval chậm +2.5 s). Ngưỡng trùng threshold panel latency để SLO line và dashboard thống nhất.
- **Cách tính error budget:** budget = 100% − 99.5% = 0.5% số request trong 28 ngày. 10,000 request → tối đa 50 request lỗi hoặc > 3000 ms; workload lab ~200 request → chỉ 1 request. SLI thực đo trong cửa sổ CP1–CP2 là 37/39 = 94.87% (2 request 3.1–4.0 s do prompt chưa tồn tại) ⇒ đã vượt budget, đó là lý do cần prompt được tạo trên Langfuse + cache, và alert `HighLatencyP95`.
- **Ba alert và runbook tương ứng:** (`config/alert_rules.yaml`, `docs/alerts.md`; Slack `#k4-l3b-alerts`, owner `student-2A202602387`) 1) `HighLatencyP95` — warning, P95 > 3000 ms trong 5m; 2) `HighErrorRateOrRetrievalFailing` — critical, error rate > 2% hoặc retrieval success < 90% trong 5m (đã chạy thử bằng practice `tool_fail`); 3) `CostPerRequestSpike` — warning, avg cost > 0.005 USD/request (≈ 2.4× baseline 0.0021) hoặc dự phóng ngày > 2.5 USD trong 10m. Mỗi runbook đi theo Metrics → Logs → Traces với lệnh cụ thể: dashboard → `scripts/log_query.py` → `scripts/trace_lookup.py`, rồi mitigation (tắt scenario, rollback prompt).

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

- **Một quyết định kỹ thuật quan trọng và lý do:** Scrub PII ở tầng processor của structlog (đệ quy mọi chuỗi, sau `format_exc_info` và trước renderer/file writer) thay vì chỉ scrub ở từng chỗ gọi `log.info`. Lý do: điểm chặn duy nhất nên log mới, `payload` lồng nhau hay stack trace đều được scrub mà không phụ thuộc người viết code nhớ gọi `summarize_text()`. Trace dùng cùng nguyên tắc: tắt `capture_input/output` và chỉ gửi preview đã scrub. Quyết định thứ hai: tách dashboard thành process riêng đọc `data/logs.jsonl`, để dashboard vẫn xem được khi chính API đang sự cố.
- **Một lỗi/blocker đã gặp:** (CP0) Sau khi điền key, `/health` báo `tracing_enabled: true` nhưng project Langfuse không có trace nào. Log API có `Failed to export spans batch ... SSLError(CERTIFICATE_VERIFY_FAILED)`, sau đó là `Read timed out`.
- **Cách tìm nguyên nhân và xử lý:** `auth_check()` qua `httpx` thành công, vì `httpx` dùng bundle `certifi`, nên key không sai. OTLP exporter lại dùng `urllib3` với SSL context mặc định, mà Python 3.13 cài từ python.org trên macOS không có `etc/openssl/cert.pem`. `urllib.request` lỗi khi chưa đặt `SSL_CERT_FILE` và trả 200 khi trỏ biến này tới `certifi.where()`. Vì vậy tôi thêm `SSL_CERT_FILE` vào `.env`. Mạng tới `cloud.langfuse.com` chậm (connect 2–3 s), còn timeout mặc định của SDK là 5 s, nên tôi đặt thêm `LANGFUSE_TIMEOUT=30`. Kết quả: lượt load test sau đó export đủ 10/10 trace. Tôi cũng ghi nhận API `GET /api/public/traces` trả 410 cho org mới, nên dùng `GET /api/public/v2/observations` để đếm trace.
- **Blocker khác (CP2):**
  1. Hai trace của lượt demo `baseline`/`candidate` không xuất hiện trên Langfuse. Cả hai là request cuối trước khi tôi dừng API để đổi label; span còn trong batch của `BatchSpanProcessor` nên bị mất khi process dừng. Xử lý: gọi `get_langfuse_client().flush()` trong phần shutdown của `lifespan` và log `tracing_flushed`; chạy lại thì trace `req-b1000002`/`req-c2000002` đều có mặt. Bài học: restart/deploy có thể làm mất telemetry của đúng những request cuối cùng.
  2. Demo promote/rollback ban đầu cho kết quả "ngược": request ngay sau khi hết TTL vẫn dùng version cũ. Đọc hành vi SDK: cache prompt kiểu stale-while-revalidate (trả bản cũ, refresh nền). Xử lý: gửi thêm một request sau TTL và ghi rõ trong runbook rằng rollback có hiệu lực sau ≈ 60s + 1 request.
  3. Panel metadata trên Langfuse UI hiện `scope.attributes.public_key` do SDK tự gắn, nên tôi không dùng ảnh metadata làm evidence mà xuất bản text bằng `scripts/trace_lookup.py` (chỉ in các key metadata an toàn).
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
