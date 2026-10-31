"""CLI/HTTP evidence regression without weights or model downloads."""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from Zipilogue import dialogue_lab
import pytest


def test_incomplete_http_outputs_preserve_report_and_exit_failure(tmp_path):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, payload))
            if self.path == '/tokenize':
                response = {'tokens': [1, 2]}
            else:
                # Valid-looking JSON with length termination must never count as agreement.
                response = {'choices': [{'finish_reason': 'length',
                                         'message': {'content': '{"mapping":[]}'}}]}
            raw = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = tmp_path / 'nested' / 'report.json'
    try:
        result = subprocess.run([
            sys.executable, '-m', 'Zipilogue.dialogue_lab', '--base-url',
            f'http://127.0.0.1:{server.server_port}', '--groups', '1', '--peers', '2',
            '--rounds', '2', '--timeout', '5', '--model-label', 'fake-length',
            '--output', str(output)], capture_output=True, text=True, timeout=30)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert result.returncode == 1, result.stderr
    report = json.loads(output.read_text())
    assert report['run_config']['model_label'] == 'fake-length'
    assert report['run_config']['request_timeout_seconds'] == 5
    group = report['groups'][0]
    assert group['status'] == 'no_agreement'
    assert group['receiver_evaluation_status'] == 'not_run_no_agreement'
    assert not group.get('positive_evidence')
    assert len(report['calls']) == 2
    assert all('incomplete model output' in call['error'] for call in report['calls'])
    assert len([path for path, _ in requests if path == '/v1/chat/completions']) == 2


def test_cli_rejects_nonpositive_timeout_before_network(tmp_path):
    with pytest.raises(SystemExit) as error:
        dialogue_lab.main(['--timeout', '0', '--output', str(tmp_path / 'unused.json')])
    assert error.value.code == 2
    assert not (tmp_path / 'unused.json').exists()
