from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from shared.llama_cmd import ask_llama


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server naming
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length).decode("utf-8"))
        prompt = req["messages"][0]["content"]
        answer = "found" if "Question:" in prompt else "none"
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": f" {answer} "}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet
        pass


def test_ask_llama_reads_first_choice_content_from_local_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        assert ask_llama("Context: x\n\nQuestion: which?", url=url) == "found"
    finally:
        server.shutdown()
        server.server_close()
