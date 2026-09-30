"""Lọc data/logs.jsonl để lấy correlation_id của request bất thường (bước Logs trong runbook).

    python scripts/log_query.py --since 15 --min-latency 3000        # request chậm
    python scripts/log_query.py --since 15 --event request_failed    # request lỗi
    python scripts/log_query.py --since 15 --min-cost 0.005          # request đắt
    python scripts/log_query.py --id req-1a2b3c4d                    # mọi dòng log của 1 request
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

COLUMNS = ("ts", "event", "correlation_id", "feature", "latency_ms", "ttft_ms", "tokens_in",
           "tokens_out", "cost_usd", "quality_score", "error_type", "tool_success")


def matches(event: dict, args: argparse.Namespace, since: datetime | None) -> bool:
    if since and datetime.fromisoformat(event["ts"].replace("Z", "+00:00")) < since:
        return False
    if args.id and event.get("correlation_id") != args.id:
        return False
    if args.event and event.get("event") != args.event:
        return False
    if args.min_latency is not None and (event.get("latency_ms") or 0) < args.min_latency:
        return False
    if args.min_cost is not None and (event.get("cost_usd") or 0) < args.min_cost:
        return False
    if args.max_quality is not None and (event.get("quality_score") is None or event["quality_score"] > args.max_quality):
        return False
    return True


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=Path("data/logs.jsonl"))
    parser.add_argument("--since", type=int, help="chỉ lấy log trong N phút gần nhất")
    parser.add_argument("--id", help="correlation_id cần xem")
    parser.add_argument("--event")
    parser.add_argument("--min-latency", type=int)
    parser.add_argument("--min-cost", type=float)
    parser.add_argument("--max-quality", type=float)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="in nguyên dòng JSON")
    args = parser.parse_args()

    since = datetime.now(timezone.utc) - timedelta(minutes=args.since) if args.since else None
    rows = []
    for line in args.log.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "ts" in event and matches(event, args, since):
            rows.append(event)

    print(f"{len(rows)} dòng khớp; hiển thị {min(len(rows), args.limit)} dòng mới nhất")
    for event in rows[-args.limit:]:
        if args.json:
            print(json.dumps(event, ensure_ascii=False))
        else:
            print(" | ".join(f"{k}={event[k]}" for k in COLUMNS if event.get(k) is not None))


if __name__ == "__main__":
    main()
