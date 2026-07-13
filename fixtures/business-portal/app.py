from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path("/data/orders.jsonl")


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"ok": True})
            return
        if self.path == "/orders":
            rows = []
            if DATA.exists():
                rows = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line]
            self._json(200, {"orders": rows})
            return
        self._json(404, {"ok": False, "error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/orders":
            self._json(404, {"ok": False, "error": "not-found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        DATA.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "id": payload.get("id") or f"order-{int(time.time() * 1000)}",
            "customer": payload.get("customer", "ifuri-customer"),
            "status": payload.get("status", "created"),
            "amount": payload.get("amount", 0),
            "ts": time.time(),
        }
        with DATA.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._json(201, row)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8010), Handler).serve_forever()
