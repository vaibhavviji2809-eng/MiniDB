from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..engine import DatabaseEngine


class QueryHandler(BaseHTTPRequestHandler):
    engine = DatabaseEngine()

    def do_POST(self):
        if self.path != "/query":
            self.send_error(404, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        sql = payload.get("sql", "")
        try:
            result = self.engine.execute(sql)
            body = json.dumps({"columns": result.columns, "rows": result.rows}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        return


def run(host: str = "127.0.0.1", port: int = 8000):
    server = ThreadingHTTPServer((host, port), QueryHandler)
    print(f"MiniDB REST API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()

