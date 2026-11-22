from __future__ import annotations

import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from shared.llama_cmd import ask_llama


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server naming
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length).decode("utf-8"))
        self.server.last_request = req
        prompt = req["messages"][0]["content"]
        answer = "found" if "Question:" in prompt else "none"
        body = json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": f" {answer} "}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output quiet
        pass


def test_ask_llama_reads_first_choice_content_from_local_server(monkeypatch):
    monkeypatch.delenv("ROUNDTRIP_SEED", raising=False)
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
        assert ask_llama("Context: x\n\nQuestion: which?", url=url) == "found"
        assert "seed" not in server.last_request
        assert server.last_request["temperature"] == 0
        monkeypatch.setenv("ROUNDTRIP_SEED", "3")
        assert ask_llama("Question:", url=url) == "found"
        assert server.last_request["seed"] == 3
        assert server.last_request["temperature"] == 0.2
    finally:
        server.shutdown()
        server.server_close()


def test_incomplete_and_invalid_answers_are_rejected():
    import pytest
    from shared.llama_cmd import extract_answer
    for reason, content in [('length', '#40'), (None, '#40'), ('stop', None), ('stop', '<think>#40'), ('stop', '')]:
        with pytest.raises(ValueError):
            extract_answer({'choices': [{'finish_reason': reason, 'message': {'content': content}}]})


def test_completed_reasoning_is_removed_before_answer_is_returned():
    from shared.llama_cmd import extract_answer
    assert extract_answer({'choices': [{'finish_reason': 'stop', 'message': {'content': '<think>#400</think>#40'}}]}) == '#40'
