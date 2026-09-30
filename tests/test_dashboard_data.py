from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.dashboard_data import compute, load_config

NOW = datetime(2026, 9, 30, 10, 30, 30, tzinfo=timezone.utc)


def _write(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _ts(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")


def test_six_panels_follow_contract_and_compute_values(tmp_path: Path) -> None:
    log = tmp_path / "logs.jsonl"
    ok = {"event": "response_sent", "tool_success": True, "ttft_ms": 50, "tokens_in": 30, "tokens_out": 100, "quality_score": 0.9}
    _write(log, [
        {"event": "request_received", "ts": _ts(90)},  # ngoài cửa sổ 60 phút
        {"event": "request_received", "ts": _ts(2)},
        {**ok, "ts": _ts(2), "latency_ms": 200, "cost_usd": 0.002},
        {"event": "request_received", "ts": _ts(1)},
        {**ok, "ts": _ts(1), "latency_ms": 4000, "cost_usd": 0.003, "quality_score": 0.5},
        {"event": "request_received", "ts": _ts(1)},
        {"event": "request_failed", "ts": _ts(1), "error_type": "RuntimeError", "tool_success": False},
    ])
    with log.open("a", encoding="utf-8") as f:
        f.write("{truncated json line\n")

    data = compute(log, load_config(), now=NOW)
    panels = {p["id"]: p for p in data["panels"]}

    assert list(panels) == ["latency", "traffic", "errors", "cost", "tokens", "quality"]
    assert data["time_range_minutes"] == 60 and len(data["minutes"]) == 61
    assert panels["latency"]["stats"]["p95"] == 4000 and panels["latency"]["status"] == "breach"
    assert panels["traffic"]["stats"]["count"] == 3
    assert panels["errors"]["stats"]["error_rate_pct"] == 33.33
    assert panels["errors"]["stats"]["tool_success_rate_pct"] == 66.67
    assert panels["errors"]["stats"]["count_by_value"] == {"RuntimeError": 1}
    assert panels["cost"]["stats"]["total"] == 0.005 and panels["cost"]["status"] == "ok"
    assert panels["tokens"]["stats"]["tokens_out"] == 200
    assert panels["quality"]["stats"]["mean"] == 0.7 and panels["quality"]["status"] == "breach"


def test_empty_log_reports_no_data(tmp_path: Path) -> None:
    data = compute(tmp_path / "missing.jsonl", load_config(), now=NOW)
    assert {p["id"]: p["status"] for p in data["panels"]}["quality"] == "no_data"
