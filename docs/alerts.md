# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Công cụ dùng chung cho cả ba runbook

Các bước bám theo luồng **Metrics → Logs → Traces**; mọi lệnh chạy từ thư mục gốc repo với `.venv` đã activate.

| Bước | Công cụ | Lệnh |
|---|---|---|
| Metrics | Dashboard 6 panel (đọc `data/logs.jsonl`, 60 phút, refresh 30s) | `python scripts/dashboard.py` → http://127.0.0.1:8050 |
| Logs | Lọc log, lấy `correlation_id` | `python scripts/log_query.py --since 15 ...` |
| Traces | Trace Langfuse có cùng `correlation_id` | `python scripts/trace_lookup.py <correlation_id> --since 30` hoặc Langfuse UI → Tracing, lọc metadata `correlation_id` |
| Prompt | Xem/đổi label prompt | `python scripts/prompt_admin.py status` / `promote --version N` |

Response lỗi 500 cũng trả `correlation_id` trong body và header `x-request-id`, nên có thể bắt đầu từ phản hồi của người dùng.

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests` (99.5% request thành công và `latency_ms <= 3000` trong 28 ngày); panel **Latency percentiles and TTFT**.
- Điều kiện và thời gian duy trì: `p95(latency_ms where event == "response_sent") > 3000` liên tục 5 phút.
- Ảnh hưởng tới người dùng: nhóm 5% request chậm nhất chờ hơn 3 giây mới có câu trả lời; mỗi request > 3000ms đốt error budget (workload 200 request chỉ có budget 1 request).
- Ba bước kiểm tra đầu tiên:
  1. Dashboard: xác nhận P95/P99 vượt đường threshold từ phút nào; so TTFT P95 — TTFT bình thường mà latency tăng nghĩa là chậm nằm ngoài bước sinh token (retrieval, prompt fetch, hàng đợi).
  2. Logs: `python scripts/log_query.py --since 15 --min-latency 3000` → chọn một `correlation_id`, kiểm tra `feature`, `tokens_in/out` có bất thường không.
  3. Traces: `python scripts/trace_lookup.py <correlation_id>` → so `latency` của `retrieval`, `prompt-resolve`, `llm-generation`. `prompt-resolve` chậm hoặc `level=WARNING` với `prompt_fetch_error` → Langfuse/mạng; `retrieval` chậm → vector store; `llm-generation` chậm với `tokens_out` cao → prompt/model.
- Mitigation tạm thời: span chậm là `prompt-resolve` → kiểm tra kết nối Langfuse, prompt vẫn phục vụ từ cache/fallback; span `retrieval` → tắt practice scenario (`python scripts/inject_incident.py --scenario rag_slow --disable`) hoặc giảm tải; generation dài bất thường sau khi đổi prompt → rollback label `production` (`python scripts/prompt_admin.py promote --version 1`, có hiệu lực sau TTL cache 60s + 1 request).
- Owner: `student-2A202602387`

## Alert 2

- Tên: `HighErrorRateOrRetrievalFailing`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: phần "thành công" của SLO `fast_successful_requests`; guardrails `error_rate_pct_max: 2` và `retrieval_success_rate_pct_min: 90`; panel **Error rate and retrieval success**.
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` **hoặc** `retrieval success < 90%` liên tục 5 phút.
- Ảnh hưởng tới người dùng: người dùng nhận HTTP 500, không có câu trả lời; mỗi lỗi đốt trực tiếp error budget nên đây là `critical`.
- Ba bước kiểm tra đầu tiên:
  1. Dashboard: đọc error rate, retrieval success và breakdown `error_type`; xác định thời điểm bắt đầu.
  2. Logs: `python scripts/log_query.py --since 15 --event request_failed` → lấy `correlation_id`, xem `error_type`, `tool_name`, `payload.detail`; `python scripts/log_query.py --id <correlation_id>` để thấy toàn bộ vòng đời request.
  3. Traces: `python scripts/trace_lookup.py <correlation_id>` → observation nào có `level=ERROR`. Ví dụ đã kiểm chứng (practice `tool_fail`): `req-946dbb90` → trace `b31805b24cff1ca01b6d65c4ca7f41f9`, span `retrieval` ERROR, không có `llm-generation` ⇒ lỗi nằm ở retrieval trước khi gọi LLM.
- Mitigation tạm thời: lỗi ở retrieval → tắt practice scenario (`python scripts/inject_incident.py --scenario tool_fail --disable`) / khôi phục vector store; lỗi xuất hiện ngay sau khi đổi prompt → rollback label `production`; xác nhận error rate về 0 trên dashboard sau 1–2 chu kỳ refresh.
- Owner: `student-2A202602387`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5`; panel **Cost over time** và **Input and output tokens**.
- Điều kiện và thời gian duy trì: `avg(cost_usd) > 0.005 USD/request` (≈ 2.4× baseline 0.0021) **hoặc** chi phí dự phóng theo ngày > 2.5 USD, liên tục 10 phút (dài hơn alert latency/error vì cost không làm người dùng chờ ngay, tránh báo động do vài request dài).
- Ảnh hưởng tới người dùng: không thấy ngay, nhưng đốt ngân sách; câu trả lời dài bất thường thường kèm latency và quality thay đổi.
- Ba bước kiểm tra đầu tiên:
  1. Dashboard: so panel cost với panel tokens — `tokens_out` tăng mà `tokens_in` giữ nguyên ⇒ model sinh dài hơn; `tokens_in` tăng ⇒ prompt/context dài hơn.
  2. Logs: `python scripts/log_query.py --since 30 --min-cost 0.005` → lấy `correlation_id`, đối chiếu `tokens_in`, `tokens_out`, `feature`.
  3. Traces: `python scripts/trace_lookup.py <correlation_id>` → đọc `usageDetails`, `costDetails`, `promptName/promptVersion` của `llm-generation` để biết prompt version nào đang chạy.
- Mitigation tạm thời: `promptVersion` vừa đổi → rollback label `production` về version trước; không liên quan prompt → tắt practice scenario (`--scenario cost_spike --disable`) hoặc giới hạn `max_tokens`; theo dõi avg cost trở về baseline.
- Owner: `student-2A202602387`
