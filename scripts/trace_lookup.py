"""Tìm trace Langfuse theo correlation_id và in cây observation (bước Traces trong runbook).

    python scripts/trace_lookup.py req-1a2b3c4d --since 30
    python scripts/trace_lookup.py --list --since 60     # danh sách trace gần đây

Dùng GET /api/public/v2/observations (org mới không còn dùng được /api/public/traces).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio

FIELDS = "core,basic,time,io,metadata,model,usage,prompt"
SHOWN = ("type", "name", "level", "startTime", "latency", "timeToFirstToken", "model",
         "usageDetails", "costDetails", "promptName", "promptVersion", "statusMessage")
METADATA_KEYS = ("correlation_id", "feature", "prompt_label", "prompt_version", "prompt_source",
                 "prompt_fetch_error", "doc_count", "query_preview", "ttft_ms")


def fetch_observations(since_minutes: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    params = {
        "fromStartTime": (now - timedelta(minutes=since_minutes)).isoformat(),
        "toStartTime": now.isoformat(),
        "limit": 1000,
        "fields": FIELDS,
    }
    response = httpx.get(
        os.environ["LANGFUSE_BASE_URL"].rstrip("/") + "/api/public/v2/observations",
        auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]),
        params=params,
        timeout=float(os.getenv("LANGFUSE_TIMEOUT", "30")),
    )
    response.raise_for_status()
    return response.json().get("data", [])


def describe(observation: dict) -> str:
    fields = {k: observation[k] for k in SHOWN if observation.get(k) not in (None, {}, "")}
    metadata = observation.get("metadata") or {}
    fields["metadata"] = {k: metadata[k] for k in METADATA_KEYS if k in metadata}
    return json.dumps(fields, ensure_ascii=False, default=str)


def main() -> None:
    configure_utf8_stdio()
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("correlation_id", nargs="?")
    parser.add_argument("--since", type=int, default=30, help="tìm trong N phút gần nhất")
    parser.add_argument("--list", action="store_true", help="liệt kê root trace gần đây")
    args = parser.parse_args()

    observations = fetch_observations(args.since)
    roots = [o for o in observations if not o.get("parentObservationId")]

    if args.list or not args.correlation_id:
        print(f"{len(roots)} trace trong {args.since} phút gần nhất")
        for root in sorted(roots, key=lambda o: o.get("startTime") or ""):
            md = root.get("metadata") or {}
            print(f"{root.get('startTime')} traceId={root['traceId']} correlation_id={md.get('correlation_id')} "
                  f"level={root.get('level')} latency_s={root.get('latency')}")
        return

    match = [o for o in roots if (o.get("metadata") or {}).get("correlation_id") == args.correlation_id]
    if not match:
        print(f"Không thấy trace cho {args.correlation_id} trong {args.since} phút (span có thể chưa được flush).")
        sys.exit(1)
    trace_id = match[0]["traceId"]
    # Root trước, con theo thời gian bắt đầu (startTime chỉ chính xác tới ms nên hay trùng nhau).
    tree = sorted(
        (o for o in observations if o["traceId"] == trace_id),
        key=lambda o: (bool(o.get("parentObservationId")), o.get("startTime") or ""),
    )
    print(f"traceId={trace_id} correlation_id={args.correlation_id}")
    for observation in tree:
        indent = "  " if observation.get("parentObservationId") else ""
        print(indent + describe(observation))


if __name__ == "__main__":
    main()
