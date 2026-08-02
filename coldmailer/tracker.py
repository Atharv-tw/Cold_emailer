"""Optional open-tracking and one-click-unsubscribe endpoint.

Only needed if you set tracking.open_tracking: true. It must be reachable on a
public HTTPS URL, ideally on the same domain you send from - a pixel loading
from an unrelated host is itself a spam signal.

Honest caveat: open tracking is unreliable. Apple Mail Privacy Protection and
Gmail's image proxy pre-fetch images, so a large share of "opens" are machines.
Replies are the metric that matters. Unsubscribe handling, on the other hand,
is worth hosting on its own.

    python -m coldmailer.tracker --config config.yaml --port 8080
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import load_config
from .store import Store

# 1x1 transparent GIF.
PIXEL = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c000000000100"
    "0100000002024401003b"
)


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        server_version = "coldmailer"

        def log_message(self, fmt: str, *args) -> None:  # quieter default logging
            pass

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlparse(self.path).path
            if path.startswith("/o/"):
                token = path[3:].removesuffix(".png").removesuffix(".gif")
                store.record_open(
                    token,
                    user_agent=self.headers.get("User-Agent", "")[:300],
                    ip=self.client_address[0],
                )
                self._send(200, PIXEL, "image/gif")
            elif path.startswith("/u/"):
                self._handle_unsub(path[3:])
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802 - RFC 8058 one-click unsubscribe
            path = urlparse(self.path).path
            if path.startswith("/u/"):
                self._handle_unsub(path[3:])
            else:
                self._send(404, b"not found", "text/plain")

        def _handle_unsub(self, token: str) -> None:
            row = store.conn.execute(
                "SELECT id, email FROM contacts WHERE unsub_token = ?", (token,)
            ).fetchone()
            if row:
                store.set_contact_status(int(row["id"]), "unsubscribed", "one-click")
                store.suppress(row["email"], reason="one-click unsubscribe")
            self._send(
                200,
                b"<html><body style='font-family:sans-serif;padding:3rem'>"
                b"<h2>You're unsubscribed.</h2><p>You won't hear from us again.</p>"
                b"</body></html>",
                "text/html; charset=utf-8",
            )

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="coldmailer tracking endpoint")
    parser.add_argument("-c", "--config", default="config.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    cfg = load_config(args.config, require_passwords=False)
    store = Store(cfg.db_path)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store))
    print(f"listening on http://{args.host}:{args.port}  (put a TLS proxy in front)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
