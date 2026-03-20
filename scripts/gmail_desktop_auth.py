#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SUCCESS_PAGE = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>Gmail Connected</title></head>
<body><h1>Authorization received</h1><p>You can close this window and return to the Email Node operator console.</p></body></html>
"""

ERROR_PAGE = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>Gmail Error</title></head>
<body><h1>Authorization failed</h1><p>Return to the terminal for details.</p></body></html>
"""


def _json_request(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _pick_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def build_handler(result_holder: dict):
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "error" in params:
                result_holder["error"] = params.get("error_description", params["error"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(ERROR_PAGE)
                return
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            if not code or not state:
                result_holder["error"] = "missing code or state in Google callback"
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(ERROR_PAGE)
                return
            result_holder["code"] = code
            result_holder["state"] = state
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SUCCESS_PAGE)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return CallbackHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run desktop Gmail OAuth for Synthia Email Node.")
    parser.add_argument("--node-base-url", default="http://10.0.0.100:9003")
    parser.add_argument("--account-id", default="primary")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()

    port = _pick_loopback_port()
    redirect_uri = f"http://127.0.0.1:{port}/oauth2callback"
    start_payload = _json_request(
        f"{args.node_base_url.rstrip('/')}/providers/gmail/accounts/{args.account_id}/connect/start",
        method="POST",
        payload={"redirect_uri": redirect_uri},
    )

    result_holder: dict[str, str] = {}
    server = ThreadingHTTPServer(("127.0.0.1", port), build_handler(result_holder))
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    connect_url = start_payload["connect_url"]
    print(f"Node base URL: {args.node_base_url}")
    print(f"Loopback redirect: {redirect_uri}")
    print(f"Open this URL to continue Google consent:\n{connect_url}\n")
    if args.open_browser:
        webbrowser.open(connect_url)

    thread.join(timeout=600)
    server.server_close()
    if "error" in result_holder:
        raise SystemExit(f"OAuth failed: {result_holder['error']}")
    if "code" not in result_holder or "state" not in result_holder:
        raise SystemExit("OAuth callback was not received before timeout.")

    completion = _json_request(
        f"{args.node_base_url.rstrip('/')}/providers/gmail/oauth/complete",
        method="POST",
        payload={"state": result_holder["state"], "code": result_holder["code"]},
    )
    print("OAuth completion accepted:")
    print(json.dumps(completion, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
