"""Quản lý prompt `day13-chat` trên Langfuse: tạo v1/v2, đổi label, xem trạng thái.

    python scripts/prompt_admin.py init                 # v1: baseline+production, v2: candidate
    python scripts/prompt_admin.py status
    python scripts/prompt_admin.py promote --version 2   # chuyển label production sang v2
    python scripts/prompt_admin.py promote --version 1   # rollback production về v1
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from app.cli import configure_utf8_stdio
from app.prompt_management import DEFAULT_PROMPT_TEMPLATE

V1_TEMPLATE = DEFAULT_PROMPT_TEMPLATE
V2_TEMPLATE = DEFAULT_PROMPT_TEMPLATE + "\nAnswer in at most 3 short bullet points and cite the doc you used."
VERSION_LABELS = {1: ["baseline"], 2: ["candidate"]}


def _client():
    from langfuse import Langfuse

    return Langfuse(timeout=int(os.getenv("LANGFUSE_TIMEOUT", "30")))


def _labels_by_version(client, name: str) -> dict[int, list[str]]:
    versions: dict[int, list[str]] = {}
    for version in range(1, 20):
        try:
            prompt = client.get_prompt(name, version=version, cache_ttl_seconds=0, max_retries=0)
        except Exception:
            break
        versions[prompt.version] = list(prompt.labels)
    return versions


def status(client, name: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] prompt '{name}'")
    for version, labels in _labels_by_version(client, name).items():
        print(f"  v{version}: labels={sorted(labels)}")


def init(client, name: str) -> None:
    existing = _labels_by_version(client, name)
    if existing:
        print(f"Prompt '{name}' đã có {len(existing)} version, bỏ qua init.")
    else:
        client.create_prompt(
            name=name, prompt=V1_TEMPLATE, labels=["baseline", "production"], type="text",
            commit_message="v1 baseline: template gốc của lab",
        )
        client.create_prompt(
            name=name, prompt=V2_TEMPLATE, labels=["candidate"], type="text",
            commit_message="v2 candidate: giới hạn câu trả lời 3 bullet + trích doc",
        )
    status(client, name)


def promote(client, name: str, version: int) -> None:
    # Label là duy nhất trong một prompt: gắn production cho version này sẽ gỡ khỏi version kia.
    client.update_prompt(name=name, version=version, new_labels=["production", *VERSION_LABELS.get(version, [])])
    print(f"production -> v{version}")
    status(client, name)


def main() -> None:
    configure_utf8_stdio()
    load_dotenv(REPO_ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "status", "promote"])
    parser.add_argument("--version", type=int)
    args = parser.parse_args()

    name = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")
    client = _client()
    if args.command == "init":
        init(client, name)
    elif args.command == "status":
        status(client, name)
    else:
        if args.version is None:
            parser.error("promote cần --version")
        promote(client, name, args.version)


if __name__ == "__main__":
    main()
