"""Tiny dependency-free web server (stdlib only) for the MeetLens UI."""
import datetime as dt
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import MeetLens
from . import report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")


def _samples():
    out = {}
    for f in sorted(os.listdir(SAMPLES)):
        if f.endswith(".txt"):
            out[f[:-4].replace("_", " ").title()] = open(os.path.join(SAMPLES, f), encoding="utf-8").read()
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, open(os.path.join(os.path.dirname(__file__), "ui.html"), encoding="utf-8").read(), "text/html")
        elif self.path == "/api/samples":
            self._send(200, json.dumps(_samples()))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/analyze":
                date = dt.date.fromisoformat(body["date"]) if body.get("date") else None
                res = MeetLens().analyze(body.get("text", ""), meeting_date=date)
                self._send(200, json.dumps(res))
            elif self.path == "/api/resolve":
                res = MeetLens().resolve(body["result"], body.get("answers", {}))
                self._send(200, json.dumps(res))
            elif self.path == "/api/export":
                fmt_, res = body.get("format", "md"), body["result"]
                text, ctype = {"md": (report.to_markdown, "text/markdown"), "html": (report.to_html, "text/html"),
                               "csv": (report.to_csv, "text/csv"), "json": (report.to_json, "application/json")}[fmt_]
                self._send(200, text(res), ctype)
            else:
                self._send(404, json.dumps({"error": "not found"}))
        except Exception as exc:  # report errors to the UI instead of dropping the connection
            self._send(400, json.dumps({"error": str(exc)}))


def serve(port=8000):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"MeetLens running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0
