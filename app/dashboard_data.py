"""Tính dữ liệu 6 panel dashboard từ data/logs.jsonl theo contract config/dashboard.yaml."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from .metrics import percentile

DASHBOARD_CONFIG = Path("config/dashboard.yaml")


def load_config(path: Path = DASHBOARD_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["dashboard"]


def load_events(log_path: Path, since: datetime) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    events = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
            ts = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if ts >= since:
            event["_minute"] = ts.replace(second=0, microsecond=0)
            events.append(event)
    return events


def _by_minute(events: list[dict], minutes: list[datetime], value) -> list[float | None]:
    buckets: dict[datetime, list[dict]] = defaultdict(list)
    for event in events:
        buckets[event["_minute"]].append(event)
    return [value(buckets[m]) if buckets[m] else None for m in minutes]


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 2) if whole else None


def _mean(values: list[float]) -> float | None:
    return round(mean(values), 4) if values else None


def _status(value: float | None, threshold: dict[str, Any]) -> str:
    if value is None:
        return "no_data"
    ok = value <= threshold["value"] if threshold["operator"] == "lte" else value >= threshold["value"]
    return "ok" if ok else "breach"


def compute(log_path: Path, config: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    window = int(config["time_range_minutes"])
    since = (now - timedelta(minutes=window)).replace(second=0, microsecond=0)
    minutes = [since + timedelta(minutes=i) for i in range(window + 1)]
    events = load_events(log_path, since)

    received = [e for e in events if e.get("event") == "request_received"]
    sent = [e for e in events if e.get("event") == "response_sent"]
    failed = [e for e in events if e.get("event") == "request_failed"]
    tool_events = [e for e in sent + failed if e.get("tool_success") is not None]

    latencies = [e["latency_ms"] for e in sent if e.get("latency_ms") is not None]
    ttfts = [e["ttft_ms"] for e in sent if e.get("ttft_ms") is not None]
    costs = [e["cost_usd"] for e in sent if e.get("cost_usd") is not None]
    quality = [e["quality_score"] for e in sent if e.get("quality_score") is not None]
    tokens_in = sum(e.get("tokens_in") or 0 for e in sent)
    tokens_out = sum(e.get("tokens_out") or 0 for e in sent)
    # Rate tính từ phút có request đầu tiên tới hiện tại: ngừng traffic thì rate giảm dần.
    first_minute = min((e["_minute"] for e in received), default=now)
    active_minutes = max(1, int((now - first_minute).total_seconds() // 60) + 1)

    values: dict[str, dict[str, Any]] = {
        "latency": {
            "stats": {
                "p50": percentile(latencies, 50),
                "p95": percentile(latencies, 95),
                "p99": percentile(latencies, 99),
                "ttft_p95": percentile(ttfts, 95),
            },
            "series": {
                "p50": _by_minute(sent, minutes, lambda b: percentile([e["latency_ms"] for e in b], 50)),
                "p95": _by_minute(sent, minutes, lambda b: percentile([e["latency_ms"] for e in b], 95)),
                "p99": _by_minute(sent, minutes, lambda b: percentile([e["latency_ms"] for e in b], 99)),
                "ttft_p95": _by_minute(sent, minutes, lambda b: percentile([e["ttft_ms"] for e in b], 95)),
            },
        },
        "traffic": {
            "stats": {"count": len(received), "rate_per_minute": round(len(received) / active_minutes, 2)},
            "series": {"requests": _by_minute(received, minutes, len)},
        },
        "errors": {
            "stats": {
                "error_rate_pct": _pct(len(failed), len(received)),
                "tool_success_rate_pct": _pct(sum(e["tool_success"] is True for e in tool_events), len(tool_events)),
                "count_by_value": dict(Counter(e.get("error_type") or "unknown" for e in failed)),
            },
            "series": {
                "error_rate_pct": _by_minute(
                    received, minutes,
                    lambda b: _pct(sum(1 for f in failed if f["_minute"] == b[0]["_minute"]), len(b)),
                ),
                "tool_success_rate_pct": _by_minute(
                    tool_events, minutes, lambda b: _pct(sum(e["tool_success"] is True for e in b), len(b))
                ),
            },
        },
        "cost": {
            "stats": {"total": round(sum(costs), 6), "avg_per_request": _mean(costs)},
            "series": {"sum_by_minute": _by_minute(sent, minutes, lambda b: round(sum(e["cost_usd"] for e in b), 6))},
        },
        "tokens": {
            "stats": {"sum_by_field": max(tokens_in, tokens_out), "tokens_in": tokens_in, "tokens_out": tokens_out},
            "series": {
                "tokens_in": _by_minute(sent, minutes, lambda b: sum(e.get("tokens_in") or 0 for e in b)),
                "tokens_out": _by_minute(sent, minutes, lambda b: sum(e.get("tokens_out") or 0 for e in b)),
            },
        },
        "quality": {
            "stats": {"mean": _mean(quality)},
            "series": {"mean": _by_minute(sent, minutes, lambda b: _mean([e["quality_score"] for e in b]))},
        },
    }

    panels = []
    for panel in config["panels"]:
        data = values[panel["id"]]
        threshold = panel["threshold"]
        headline = data["stats"].get(threshold["aggregation"])
        panels.append(
            {
                "id": panel["id"],
                "title": panel["title"],
                "unit": panel["unit"],
                "query": panel["query"],
                "threshold": threshold,
                "headline": headline,
                "status": _status(headline, threshold),
                **data,
            }
        )

    return {
        "title": config["title"],
        "source": str(log_path),
        "time_range_minutes": window,
        "refresh_seconds": config["refresh_seconds"],
        "window_start": since.isoformat(),
        "generated_at": now.isoformat(timespec="seconds"),
        "minutes": [m.strftime("%H:%M") for m in minutes],
        "event_count": len(events),
        "panels": panels,
    }
