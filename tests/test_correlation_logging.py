from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app

REQUEST_ID = re.compile(r"^req-[0-9a-f]{8}$")
ENRICHMENT = ("user_id_hash", "session_id", "feature", "model", "env")


def _chat(requests: list[tuple[dict, dict]]) -> list[httpx.Response]:
    async def send() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return [await client.post("/chat", json=body, headers=headers) for body, headers in requests]

    return asyncio.run(send())


def _body(user: str, message: str = "Explain observability") -> dict:
    return {"user_id": user, "session_id": f"s-{user}", "feature": "qa", "message": message}


def _events(log_path: Path) -> list[dict]:
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]


def test_generates_and_returns_correlation_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    (response,) = _chat([(_body("u1"), {})])

    cid = response.headers["x-request-id"]
    assert REQUEST_ID.match(cid)
    assert response.json()["correlation_id"] == cid
    assert float(response.headers["x-response-time-ms"]) >= 0


def test_propagates_valid_and_replaces_invalid_request_id(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    valid, invalid = _chat(
        [
            (_body("u1"), {"x-request-id": "req-0badc0de"}),
            (_body("u2"), {"x-request-id": "student@vinuni.edu.vn"}),
        ]
    )

    assert valid.headers["x-request-id"] == "req-0badc0de"
    assert REQUEST_ID.match(invalid.headers["x-request-id"])
    assert "@" not in invalid.headers["x-request-id"]


def test_logs_are_enriched_without_context_leakage(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    first, second = _chat([(_body("alice"), {}), (_body("bob"), {})])

    api_events = [e for e in _events(log_path) if e.get("service") == "api"]
    assert len(api_events) == 4
    for event in api_events:
        assert all(event.get(field) for field in ENRICHMENT), event
        assert REQUEST_ID.match(event["correlation_id"])

    by_cid: dict[str, set[str]] = {}
    for event in api_events:
        by_cid.setdefault(event["correlation_id"], set()).add(event["session_id"])
    assert by_cid == {
        first.headers["x-request-id"]: {"s-alice"},
        second.headers["x-request-id"]: {"s-bob"},
    }


def test_raw_pii_never_reaches_log_file(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    message = "Email student@vinuni.edu.vn, phone 090 123 4567, CCCD 001203004567, card 4111 1111 1111 1111"

    _chat([(_body("u1", message), {})])
    logging_config.get_logger().info(
        "nested_check", service="test", payload={"nested": {"items": ["mail a@b.co"]}}
    )

    raw = log_path.read_text(encoding="utf-8")
    for secret in ("student@vinuni.edu.vn", "090 123 4567", "001203004567", "4111 1111", "a@b.co"):
        assert secret not in raw
    assert "REDACTED_EMAIL" in raw


def test_failed_request_returns_correlation_id(monkeypatch, tmp_path: Path) -> None:
    from app import incidents

    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setitem(incidents.STATE, "tool_fail", True)

    (response,) = _chat([(_body("u1"), {})])

    assert response.status_code == 500
    cid = response.headers["x-request-id"]
    assert response.json() == {"detail": "RuntimeError", "correlation_id": cid}
    failed = next(e for e in _events(log_path) if e["event"] == "request_failed")
    assert failed["correlation_id"] == cid
    assert failed["tool_success"] is False


def test_concurrent_requests_are_not_serialized(monkeypatch, tmp_path: Path) -> None:
    import time

    from app import incidents

    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")
    monkeypatch.setitem(incidents.STATE, "rag_slow", True)

    async def send_concurrently() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await asyncio.gather(*(client.post("/chat", json=_body(f"u{i}")) for i in range(3)))

    started = time.perf_counter()
    responses = asyncio.run(send_concurrently())
    elapsed = time.perf_counter() - started

    assert all(r.status_code == 200 for r in responses)
    # rag_slow thêm 2.5s/request: tuần tự sẽ ≥ 7.5s, song song chỉ ≈ 2.7s.
    assert elapsed < 5
    events = _events(tmp_path / "logs.jsonl")
    assert len({e["correlation_id"] for e in events if e["event"] == "response_sent"}) == 3
    assert all(e.get("session_id") for e in events if e["event"] == "response_sent")
