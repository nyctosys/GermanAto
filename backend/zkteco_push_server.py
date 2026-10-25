#!/usr/bin/env python3
"""
ZKTeco PUSH protocol test server.

The device (client) sends HTTP requests to this server. Use this to verify
that the device in T&A PUSH mode can reach your server and to inspect
the payloads it sends.

Protocol (ZKTeco PUSH):
  - GET  /iclock/getrequest?SN=<serial>     → device heartbeat / poll for commands
  - POST /iclock/cdata?SN=<serial>&table=<TABLE>&Stamp=<ts>  → push data (body = tab-separated)

Tables: ATTLOG (attendance), OPERLOG (operations/users), etc.
Server must respond with plain text "OK".

Run from backend: python zkteco_push_server.py [--port 5001]
On the device, set Cloud Server Address to this machine's IP and port to match (e.g. 5001).
If port is in use, try: python zkteco_push_server.py --port 5002
"""

import argparse
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

# Use 5001 so Flask can stay on 5000; set Cloud Server port on device to match.
DEFAULT_PORT = 5000


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] [{level}] {msg}", flush=True)


def _parse_options_line(line: str) -> dict:
    """Parse options table body: key=value,key=value,... (values may contain commas)."""
    result = {}
    # Simple split on , then = for each part (keys don't have =)
    for part in line.split(","):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            result[k.strip()] = v.strip()
    return result


class ZKTecoPushHandler(BaseHTTPRequestHandler):
    """Handles ZKTeco PUSH protocol endpoints."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/iclock/getrequest":
            sn = qs.get("SN", ["?"])[0]
            log(f"GET /iclock/getrequest  SN={sn!r}  (device heartbeat)")
            self._send_ok()
            return

        if path == "/iclock/cdata":
            sn = qs.get("SN", ["?"])[0]
            opts = qs.get("options", [""])[0]
            log(f"GET /iclock/cdata  SN={sn!r}  options={opts!r}")
            self._send_ok()
            return

        log(f"GET  {path}  query={parsed.query}")
        self._send_ok()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/iclock/cdata":
            sn = qs.get("SN", ["?"])[0]
            table = qs.get("table", ["?"])[0]
            stamp = qs.get("Stamp", ["?"])[0]
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length else b""
            try:
                body_text = body.decode("utf-8", errors="replace")
            except Exception:
                body_text = "<binary>"

            log(f"POST /iclock/cdata  SN={sn!r}  table={table!r}  Stamp={stamp!r}")
            if body_text.strip():
                attlog_count = 0
                for line in body_text.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t")
                    if table == "ATTLOG" and len(parts) >= 3:
                        attlog_count += 1
                        punch_label = "IN" if parts[2] == "0" else "OUT"
                        log(f"  >>> ATTENDANCE: user_id={parts[0]!r}  time={parts[1]!r}  punch={punch_label}", level="INFO")
                    elif table == "OPERLOG" and parts:
                        op = parts[0] if parts else "?"
                        t = parts[2] if len(parts) > 2 else "?"
                        log(f"  OPERLOG: {op}  at {t}")
                    elif table == "options":
                        opts = _parse_options_line(line)
                        for key in ("DeviceName", "MAC", "IPAddress", "FWVersion", "UserCount", "TransactionCount"):
                            val = opts.get(key) or opts.get("~" + key)
                            if val is not None:
                                log(f"  options {key}={val!r}")
                    else:
                        log(f"  raw: {line[:120]!r}" + ("..." if len(line) > 120 else ""))
                if table == "ATTLOG" and attlog_count > 0:
                    log(f"  --- Received {attlog_count} attendance record(s) ---", level="INFO")
            else:
                log("  (empty body)")

            self._send_ok()
            return

        log(f"POST {path}  query={parsed.query}")
        self._send_ok()

    def _send_ok(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", 2)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # Suppress default request log; we log in handlers
        pass


def run_server(host: str, port: int) -> None:
    try:
        server = HTTPServer((host, port), ZKTecoPushHandler)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            log(f"Port {port} is already in use (e.g. by Flask). Run: python zkteco_push_server.py --port {port + 1}", level="ERROR")
        else:
            log(f"Failed to bind: {e}", level="ERROR")
        sys.exit(1)
    log(f"ZKTeco PUSH test server listening on http://{host}:{port}")
    log("Endpoints: GET/POST /iclock/getrequest, POST /iclock/cdata")
    log("On device set Cloud Server to this host and port, then restart device.")
    log("To test attendance: punch IN or OUT on the device; ATTLOG will appear here.")
    log("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down.")
        server.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test server for ZKTeco PUSH protocol (device pushes to this server).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        "-H",
        default="0.0.0.0",
        help="Bind address (0.0.0.0 for all interfaces)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=DEFAULT_PORT,
        help="Port for device to connect to (set same in device Cloud Server)",
    )
    args = parser.parse_args()
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
