"""Dashboard runtime 6 panel đọc data/logs.jsonl (chạy tách khỏi API).

    python scripts/dashboard.py            # http://127.0.0.1:8050
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.dashboard_data import compute, load_config

PAGE = REPO_ROOT / "scripts" / "dashboard.html"


def make_handler(log_path: Path, config_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                body, content_type = PAGE.read_bytes(), "text/html; charset=utf-8"
            elif self.path.startswith("/data"):
                payload = compute(log_path, load_config(config_path))
                body, content_type = json.dumps(payload).encode(), "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("content-type", content_type)
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:
            return

    return Handler


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--log", type=Path, default=Path("data/logs.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("config/dashboard.yaml"))
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.log, args.config))
    print(f"Dashboard: http://127.0.0.1:{args.port}  (source: {args.log})")
    server.serve_forever()


if __name__ == "__main__":
    main()
